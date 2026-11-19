from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.parse import urljoin, urlencode, urlparse
from urllib.robotparser import RobotFileParser
from bs4 import BeautifulSoup
from .core import Tip, LISBON, UTC, iso_time, name_key, team_equal
import json
import os
import re
import threading

USER_AGENT = "MisterMi/1.0 (+https://github.com/juliomcm-tech/mister-mi)"
SPORTS = {"Football": "football", "Tennis": "tennis", "Basketball": "basketball", "Ice_Hockey": "hockey", "American_Football": "american_football"}
OLBG_URLS = ["https://www.olbg.com/betting-tips/" + path for path in
             ["Football/1", "Tennis/3", "Basketball/4", "Ice_Hockey/13", "American_Football/11"]]
FOREBET_PAGES = [
    ("https://www.forebet.com/en/football-tips-and-predictions-for-today", "football", "FT_1X2"),
    ("https://www.forebet.com/en/football-tips-and-predictions-for-today/predictions-under-over-goals", "football", "FT_TOTAL_2.5"),
    ("https://www.forebet.com/en/tennis/predictions-today", "tennis", "MATCH_WINNER"),
    ("https://www.forebet.com/en/basketball/predictions-today", "basketball", "MATCH_WINNER"),
    ("https://www.forebet.com/en/hockey/predictions-today", "hockey", "FT_1X2"),
]


class FetchError(RuntimeError):
    pass


class SameHostRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        if urlparse(request.full_url).netloc != urlparse(newurl).netloc or urlparse(newurl).scheme != "https":
            raise FetchError("Redirecionamento para outro domínio bloqueado")
        return super().redirect_request(request, fp, code, message, headers, newurl)


class Client:
    def __init__(self):
        self.robots = {}
        self.lock = threading.Lock()

    def get(self, url: str, *, headers=None, check_robots=True) -> str:
        host = urlparse(url).netloc
        if check_robots:
            # Fail closed when robots cannot be checked. No stealth or access bypass.
            with self.lock:
                if host not in self.robots:
                    robot = RobotFileParser()
                    robot.parse(self.get(f"https://{host}/robots.txt", check_robots=False).splitlines())
                    self.robots[host] = robot
                robot = self.robots[host]
            if not robot.can_fetch(USER_AGENT, url):
                raise FetchError("Recolha não permitida pelo robots.txt")
        req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*", **(headers or {})})
        try:
            with build_opener(SameHostRedirect()).open(req, timeout=18) as response:
                if urlparse(response.url).netloc != host:
                    raise FetchError("Redirecionamento para outro domínio")
                raw = response.read(5_000_001)
                if len(raw) > 5_000_000:
                    raise FetchError("Resposta demasiado grande")
                return raw.decode("utf-8", errors="replace")
        except FetchError:
            raise
        except Exception as exc:
            # Never put tokens, query strings, or remote response bodies into logs.
            code = getattr(exc, "code", None)
            raise FetchError(f"HTTP {code}" if code else f"Falha de ligação ({type(exc).__name__})") from None


def text(node, selector):
    result = node.select_one(selector)
    return result.get_text(" ", strip=True) if result else ""


def number(value):
    try:
        n = float(str(value).replace("%", "").replace(",", "."))
        return n if 0 <= n < 1_000_000 else None
    except (TypeError, ValueError):
        return None


def segment_for(competition, home, away):
    s = name_key(" ".join([competition, home, away]))
    tags = re.findall(r"\b(?:w|u\d{2}|reserves)\b", s)
    return ":".join(sorted(set(tags))) or "open"


def country_for(value):
    countries = ["United States", "South Korea", "South Africa", "Saudi Arabia", "Czech Republic", "Northern Ireland",
                 "England", "Scotland", "Wales", "Ireland", "Portugal", "Spain", "France", "Germany", "Italy", "Brazil",
                 "Argentina", "Uruguay", "Chile", "Colombia", "Ecuador", "Mexico", "Canada", "Australia", "Japan", "China",
                 "Netherlands", "Belgium", "Austria", "Switzerland", "Denmark", "Sweden", "Norway", "Finland", "Poland",
                 "Turkey", "Greece", "Romania", "Croatia", "Serbia", "Bulgaria", "Syria", "Egypt", "India", "Thailand"]
    return next((c for c in countries if value.lower().startswith(c.lower())), "Desconhecido")


def market_selection(label, selection, home, away, sport):
    m, s = name_key(label), name_key(selection)
    if m in {"full time result", "match result", "team to win", "win match", "match winner", "moneyline", "money line", "to win"}:
        market = "FT_1X2" if sport == "football" or m == "full time result" else "MATCH_WINNER"
        if s in {"1", "home"} or team_equal(selection, home, sport):
            return market, "HOME"
        if s in {"2", "away"} or team_equal(selection, away, sport):
            return market, "AWAY"
        if s in {"x", "draw"}:
            return market, "DRAW"
    if sport == "football" and re.fullmatch(r"(?:goals total|total goals|over under)(?: \d \d)?", m):
        match = re.search(r"(1\.5|2\.5|3\.5)", label + " " + selection)
        if match and (s.startswith("over") or s.startswith("under")):
            return "FT_TOTAL_" + match[1], "OVER" if s.startswith("over") else "UNDER"
    if sport == "football" and m in {"both teams to score", "both teams score"} and s in {"yes", "no"}:
        return "FT_BTTS", s.upper()
    return None


def parse_olbg(html, url, now):
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select(".grd.tip")
    if not rows:
        raise FetchError("Estrutura OLBG alterada: não foram encontradas linhas de tips")
    result = []
    for row in rows:
        try:
            event = row.select_one(".ev a[itemprop=url]")
            dt = row.select_one("time[datetime]")
            if not event or not dt:
                continue
            event_url = urljoin(url, event["href"])
            sport = next((v for k, v in SPORTS.items() if f"/betting-tips/{k}/" in event_url), None)
            event_name = event.get_text(" ", strip=True)
            parts = re.split(r"\s+(?:v|vs|@)\s+", event_name, flags=re.I)
            if sport is None or len(parts) != 2:
                continue
            # In the explicit American notation, visitor @ host: reverse both sides once.
            home, away = reversed(parts) if " @ " in event_name else parts
            kickoff = iso_time(dt["datetime"])
            competition = text(row, ".ev p")
            selection = text(row, ".sel h4")
            market = market_selection(text(row, ".sel p"), selection, home, away, sport)
            votes = re.search(r"(\d+)\s*/\s*(\d+)\s*Win Tips", text(row, ".tips"))
            if not market or not votes or int(votes[2]) == 0:
                continue
            odds_node = row.select_one("[data-decimal]")
            result.append(Tip("olbg", sport, home, away, kickoff.astimezone(LISBON).date().isoformat(),
                              kickoff.isoformat(), *market, event_url, now.isoformat(), competition,
                              round(100 * int(votes[1]) / int(votes[2]), 2), "vote_pct", int(votes[1]), int(votes[2]),
                              number(odds_node.get("data-decimal")) if odds_node else None,
                              segment=segment_for(competition, home, away), country=country_for(competition)))
        except (ValueError, TypeError, KeyError):
            continue
    return result, len(rows), 0


def parse_forebet(html, url, now, sport="football", market="FT_1X2"):
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select(".rcnt")
    if not rows:
        raise FetchError("Estrutura Forebet alterada ou sem jogos publicados")
    result = []
    for row in rows:
        try:
            home, away = text(row, ".homeTeam"), text(row, ".awayTeam")
            raw_date = text(row, ".date_bah")
            # Forebet's all.js shifts its raw HTML dates from UTC+2 (offset includes 120 minutes).
            # Parse HTML, not browser-adjusted text. Keep this explicit and covered by a regression test.
            kickoff = datetime.strptime(raw_date, "%d/%m/%Y %H:%M").replace(tzinfo=timezone(timedelta(hours=2))).astimezone(UTC)
            pred = text(row, ".predict .forepr")
            probs = [number(x.get_text(strip=True)) for x in row.select(".fprc > span")]
            if not home or not away or not probs or any(x is None for x in probs):
                continue
            if sport == "hockey" and len(probs) != 3:
                continue  # Two-way winner scope is not interchangeable with regulation 1X2.
            if abs(sum(probs) - 100) > 2:
                continue
            if market.startswith("FT_TOTAL_"):
                # Columns are Under, Over. Use probability of the predicted selection, never max().
                outcome = {"Under": "UNDER", "Over": "OVER"}.get(pred)
                index = {"UNDER": 0, "OVER": 1}.get(outcome)
            else:
                order = {"1": ("HOME", 0), "X": ("DRAW", 1), "2": ("AWAY", 2 if len(probs) == 3 else 1)}
                outcome, index = order.get(pred.upper(), (None, None))
            if index is None or index >= len(probs):
                continue
            link = row.select_one(".tnmscn[href]")
            competition = row.select_one(".flsc")
            league = competition.get("onclick", "") if competition else ""
            parts = re.findall(r"'([^']*)'", league)
            league = " · ".join(parts[:2])
            live = text(row, ".l_min")
            result.append(Tip("forebet", sport, home, away, kickoff.astimezone(LISBON).date().isoformat(),
                              kickoff.isoformat(), market, outcome, urljoin(url, link["href"]) if link else url,
                              now.isoformat(), league, probs[index], "model_pct",
                              odds=number(text(row, ".lscrsp")), segment=segment_for(league, home, away),
                              status="live" if live else "scheduled", country=country_for(league)))
        except (ValueError, TypeError, KeyError):
            continue
    return result, len(rows), 0


def parse_protipster(html, url, now):
    # Public hydration data is JSON inside a JS wrapper. Decode JSON only; never eval JavaScript.
    match = re.search(r"mutation:\s*['\"]TIPS_SECTIONS['\"]\s*,\s*args:\s*\[\s*", html)
    if not match:
        raise FetchError("Dados públicos ProTipster indisponíveis ou estrutura alterada")
    try:
        sections, _ = json.JSONDecoder().raw_decode(html[match.end():])
    except ValueError:
        raise FetchError("JSON ProTipster inválido") from None
    raw = [tip for section in sections.values() if isinstance(section, dict) for tip in section.get("picks", [])]
    result, missing_score = [], 0
    for item in raw:
        try:
            home, away = item["hostName"], item["opponentName"]
            sport = {"football": "football", "tennis": "tennis", "basketball": "basketball", "ice-hockey": "hockey"}.get(item["sportSlug"])
            if not sport or item.get("cancelled") or item.get("postponed"):
                continue
            market = market_selection(item.get("marketPhrase", ""), item.get("outcome", ""), home, away, sport)
            if not market:
                continue
            kickoff = iso_time(item["fixtureDate"])
            tip_score = number(item.get("tipScore", item.get("tip_score")))
            if tip_score is None:
                missing_score += 1
            competition = item.get("tournamentName", "")
            result.append(Tip("protipster", sport, home, away, kickoff.astimezone(LISBON).date().isoformat(),
                              kickoff.isoformat(), *market, url, now.isoformat(), competition, tip_score,
                              "tip_score" if tip_score is not None else "missing", odds=number(item.get("currentRawOdd")),
                              event_id=str(item["fixtureId"]), segment=segment_for(competition, home, away),
                              status="live" if item.get("fixtureState", {}).get("currentMatchTime") else "scheduled",
                              country=country_for(item.get("categoryName", ""))))
        except (ValueError, TypeError, KeyError):
            continue
    return result, len(raw), missing_score


def parse_predictz(html, url, now):
    soup = BeautifulSoup(html, "html.parser")
    # This page does not expose kickoff times. Its explicit full date can only corroborate timed anchors.
    title = soup.get_text(" ", strip=True)
    date_match = re.search(r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+([A-Za-z]+) (\d{1,2})(?:st|nd|rd|th), (\d{4})", title)
    if not date_match:
        raise FetchError("PredictZ: data completa não publicada")
    event_date = datetime.strptime(f"{date_match[1]} {date_match[2]} {date_match[3]}", "%B %d %Y").date().isoformat()
    rows = soup.select(".pttr.ptcnt")
    result = []
    for row in rows:
        home, away = text(row, ".ptmobh"), text(row, ".ptmoba")
        prediction = text(row, ".ptpredboxsml")
        outcome = next((v for k, v in {"Home": "HOME", "Away": "AWAY", "Draw": "DRAW"}.items() if prediction.startswith(k + " ")), None)
        link = row.select_one(".ptgame a[href]")
        if home and away and outcome and link:
            result.append(Tip("predictz", "football", home, away, event_date, None, "FT_1X2", outcome,
                              urljoin(url, link["href"]), now.isoformat(), segment=segment_for("", home, away)))
    if not result:
        raise FetchError("Estrutura PredictZ alterada ou sem prognósticos")
    return result, len(result), 0


def api_football(client, now, candidates):
    key = os.environ.get("API_FOOTBALL_KEY")
    if not key:
        return [], {"id": "api_football", "name": "API-Football", "status": "not_configured", "message": "Opcional · requer chave API", "collected": 0, "raw_rows": 0}
    base = "https://v3.football.api-sports.io/"
    headers = {"x-apisports-key": key}
    day = now.astimezone(LISBON).date().isoformat()
    response = json.loads(client.get(base + "fixtures?" + urlencode({"date": day, "timezone": "Europe/Lisbon"}), headers=headers, check_robots=False))
    if response.get("errors"):
        raise FetchError("API-Football: verificar chave, plano ou limite de pedidos")
    fixtures = response.get("response", [])
    result, calls = [], 0
    limit = min(20, max(0, int(os.environ.get("API_FOOTBALL_MAX_FIXTURES", "10"))))
    for fixture in fixtures:
        home, away = fixture["teams"]["home"]["name"], fixture["teams"]["away"]["name"]
        if fixture["fixture"]["status"]["short"] not in {"NS", "TBD"}:
            continue
        if not any(t.sport == "football" and t.event_date == day and team_equal(t.home, home, "football") and team_equal(t.away, away, "football") for t in candidates):
            continue
        if calls >= limit:
            break
        calls += 1
        data = json.loads(client.get(base + "predictions?fixture=" + str(int(fixture["fixture"]["id"])), headers=headers, check_robots=False))
        if data.get("errors"):
            raise FetchError("API-Football: falha nas previsões; verificar cobertura e quota")
        for p in data.get("response", []):
            percentages = p.get("predictions", {}).get("percent", {})
            for outcome, field in [("HOME", "home"), ("DRAW", "draw"), ("AWAY", "away")]:
                metric = number(percentages.get(field))
                if metric is not None and metric >= 65:
                    kickoff = iso_time(fixture["fixture"]["date"])
                    competition = fixture["league"]["name"]
                    result.append(Tip("api_football", "football", home, away, kickoff.astimezone(LISBON).date().isoformat(),
                                      kickoff.isoformat(), "FT_1X2", outcome, "https://www.api-football.com/", now.isoformat(),
                                      competition, metric, "model_pct", event_id=str(fixture["fixture"]["id"]),
                                      segment=segment_for(competition, home, away), country=country_for(fixture["league"].get("country", ""))))
    return result, {"id": "api_football", "name": "API-Football", "status": "ok", "message": f"{calls} jogos consultados · limite {limit}", "collected": len(result), "raw_rows": len(fixtures)}


def collect(now):
    client = Client()
    jobs = [("olbg", u, parse_olbg, {}) for u in OLBG_URLS]
    jobs += [("forebet", u, parse_forebet, {"sport": sport, "market": market}) for u, sport, market in FOREBET_PAGES]
    jobs += [("protipster", "https://www.protipster.com/betting-tips/today", parse_protipster, {}),
             ("predictz", "https://www.predictz.com/predictions/", parse_predictz, {})]
    tips, logs = [], []

    def run(job):
        source, url, parser, kwargs = job
        try:
            html = client.get(url)
            data, rows, missing = parser(html, url, datetime.now(UTC), **kwargs)
            partial = bool(missing or rows and not data)
            return data, {"id": source, "url": url, "status": "partial" if partial else "ok", "raw_rows": rows,
                          "collected": len(data), "missing_scores": missing,
                          "message": f"{missing} tips sem Tip Score público; excluídas do consenso" if missing else
                          "Sem mercados suportados nas linhas publicadas" if rows and not data else "Recolha concluída"}
        except Exception as exc:
            message = str(exc) if isinstance(exc, FetchError) else f"Falha do adaptador ({type(exc).__name__})"
            return [], {"id": source, "url": url, "status": "error", "raw_rows": 0, "collected": 0, "message": message}

    with ThreadPoolExecutor(max_workers=4) as pool:
        for future in as_completed([pool.submit(run, job) for job in jobs]):
            data, log = future.result()
            tips.extend(data)
            logs.append(log)
    sources = []
    for source, name in [("olbg", "OLBG"), ("forebet", "Forebet"), ("protipster", "ProTipster"), ("predictz", "PredictZ")]:
        pages = sorted([log for log in logs if log["id"] == source], key=lambda x: x["url"])
        statuses = {x["status"] for x in pages}
        status = "ok" if statuses == {"ok"} else "error" if statuses == {"error"} else "partial"
        sources.append({"id": source, "name": name, "status": status, "collected": sum(x["collected"] for x in pages),
                        "raw_rows": sum(x["raw_rows"] for x in pages), "message": next((p["message"] for p in pages if p["status"] != "ok"), "Recolha concluída"), "pages": pages})
    try:
        data, status = api_football(client, now, tips)
        tips.extend(data)
        sources.append(status)
    except Exception as exc:
        sources.append({"id": "api_football", "name": "API-Football", "status": "error", "collected": 0,
                        "message": str(exc) if isinstance(exc, FetchError) else "Falha ao consultar API-Football"})
    return tips, sources
