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
                    try:
                        robot.parse(self.get(f"https://{host}/robots.txt", check_robots=False).splitlines())
                    except FetchError as exc:
                        # RFC 9309: robots.txt inexistente (404/410) significa sem restrições.
                        # Qualquer outra falha (403, 5xx, rede) continua a bloquear a recolha.
                        if str(exc) not in {"HTTP 404", "HTTP 410"}:
                            raise
                        robot.parse([])
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


def _olbg_public_tips(soup):
    """Read the bounded literal sent to every public page, without running JavaScript.

    OLBG renders only the first 20 tips, while its Svelte page data can already
    contain 100. Only JSON values plus unquoted object keys are accepted here;
    references, calls, functions and other executable expressions fail closed.
    A changed/unsupported payload falls back to the rendered rows.
    """
    def reject_constant(value):
        raise ValueError("Constante JSON não suportada")

    for script in soup.find_all("script", src=False):
        source = script.get_text()
        if "__sveltekit_" not in source or "kit.start(" not in source:
            continue
        match = re.search(r"\bdata\s*:\s*\{\s*tips\s*:\s*(\[)", source)
        if not match:
            continue
        start = match.start(1)
        depth, quoted, escaped = 0, False, False
        for end in range(start, min(len(source), start + 2_000_000)):
            char = source[end]
            if quoted:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    quoted = False
            elif char == '"':
                quoted = True
            elif char == "[":
                depth += 1
            elif char == "]":
                depth -= 1
                if depth == 0:
                    literal = source[start:end + 1]
                    # Match quoted strings FIRST, leaving every escaped value intact.
                    literal = re.sub(r'("(?:\\.|[^"\\])*")|([A-Za-z_$][\w$]*)(?=\s*:)',
                                     lambda m: m[1] or json.dumps(m[2]), literal)
                    try:
                        rows = json.loads(literal, parse_constant=reject_constant)
                    except (ValueError, RecursionError):
                        return None
                    return rows if isinstance(rows, list) and len(rows) <= 1000 and all(isinstance(x, dict) for x in rows) else None
    return None


def _olbg_event(url, event_url, event_name):
    if not isinstance(event_url, str) or not isinstance(event_name, str):
        raise ValueError("Evento OLBG inválido")
    event_url = urljoin(url, event_url)
    parsed = urlparse(event_url)
    if parsed.scheme != "https" or parsed.netloc != "www.olbg.com":
        raise ValueError("Evento fora do domínio OLBG")
    sport = next((v for k, v in SPORTS.items() if parsed.path.startswith(f"/betting-tips/{k}/")), None)
    parts = re.split(r"\s+(?:v|vs|@)\s+", event_name.strip(), flags=re.I)
    if sport is None or len(parts) != 2 or not all(part.strip() for part in parts):
        raise ValueError("Participantes ou desporto OLBG inválidos")
    # Explicit American notation is visitor @ host, in both HTML and page data.
    home, away = reversed(parts) if " @ " in event_name else parts
    return event_url, sport, home.strip(), away.strip()


def _olbg_tip_key(tip):
    return (tip.sport, name_key(tip.home), name_key(tip.away), tip.kickoff, tip.market, tip.outcome, tip.segment, tip.country)


def _olbg_raw_key(url, event_url, stamp, label, selection, competition):
    """Count each public market row once, before status/market validation."""
    event_url = urljoin(url, event_url) if isinstance(event_url, str) else repr(event_url)
    try:
        stamp = float(stamp)
    except (TypeError, ValueError, OverflowError):
        stamp = repr(stamp)
    return (event_url, stamp, repr(label), repr(selection), repr(competition or ""))


def parse_olbg(html, url, now):
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select(".grd.tip")
    public_rows = _olbg_public_tips(soup)
    if not rows and not public_rows:
        raise FetchError("Estrutura OLBG alterada: não foram encontradas linhas de tips")
    result, raw_keys, rendered_keys = [], set(), {}
    for index, row in enumerate(rows):
        try:
            event = row.select_one(".ev a[itemprop=url]")
            dt = row.select_one("time[datetime]")
            if not event or not dt:
                raw_keys.add(("html-invalid", index))
                continue
            try:
                raw_stamp = iso_time(dt["datetime"]).timestamp()
            except (ValueError, TypeError):
                raw_stamp = dt.get("datetime")
            raw_key = _olbg_raw_key(url, event.get("href"), raw_stamp, text(row, ".sel p"), text(row, ".sel h4"), text(row, ".ev p"))
            raw_keys.add(raw_key)
            event_name = event.get_text(" ", strip=True)
            event_url, sport, home, away = _olbg_event(url, event["href"], event_name)
            kickoff = iso_time(dt["datetime"])
            competition = text(row, ".ev p")
            selection = text(row, ".sel h4")
            market = market_selection(text(row, ".sel p"), selection, home, away, sport)
            votes = re.search(r"(\d+)\s*/\s*(\d+)\s*Win Tips", text(row, ".tips"))
            if not market or not votes or int(votes[2]) == 0 or int(votes[1]) > int(votes[2]):
                continue
            odds_node = row.select_one("[data-decimal]")
            result.append(Tip("olbg", sport, home, away, kickoff.astimezone(LISBON).date().isoformat(),
                              kickoff.isoformat(), *market, event_url, now.isoformat(), competition,
                              round(100 * int(votes[1]) / int(votes[2]), 2), "vote_pct", int(votes[1]), int(votes[2]),
                              number(odds_node.get("data-decimal")) if odds_node else None,
                              segment=segment_for(competition, home, away), country=country_for(competition)))
            rendered_keys.setdefault(raw_key, set()).add(_olbg_tip_key(result[-1]))
        except (ValueError, TypeError, KeyError):
            continue
    # Keep rendered values for repeated rows; loading more of the same community
    # never adds a source, sums votes or creates a second confirmation.
    unique = {_olbg_tip_key(tip): tip for tip in result}
    blocked_keys, public_raw_keys = set(), set()
    for item in public_rows or []:
        try:
            raw_key = _olbg_raw_key(url, item.get("eventUrl"), item.get("event_start_unix_timestamp"),
                                    item.get("market_alias"), item.get("selection"), item.get("menu_league"))
            raw_keys.add(raw_key)
            public_raw_keys.add(raw_key)
            inactive = item.get("expired") or item.get("cancelled") or item.get("postponed")
            if inactive:
                for key in rendered_keys.get(raw_key, set()):
                    blocked_keys.add(key)
                    unique.pop(key, None)
            event_url, sport, home, away = _olbg_event(url, item["eventUrl"], item["event_name_alias"])
            stamp = item["event_start_unix_timestamp"]
            if isinstance(stamp, bool) or not isinstance(stamp, (int, float)) or stamp <= 0:
                continue
            kickoff = datetime.fromtimestamp(stamp, UTC)
            votes_for, votes_total = item["win_tips"], item["win_tips_count"]
            if (type(votes_for) is not int or type(votes_total) is not int
                    or not 0 <= votes_for <= votes_total or votes_total <= 0):
                continue
            selection, label = item["selection"], item["market_alias"]
            competition = item.get("menu_league") or ""
            if not all(isinstance(value, str) for value in (selection, label, competition)):
                continue
            market = market_selection(label, selection, home, away, sport)
            if not market:
                continue
            tip = Tip("olbg", sport, home, away, kickoff.astimezone(LISBON).date().isoformat(),
                      kickoff.isoformat(), *market, event_url, now.isoformat(), competition,
                      round(100 * votes_for / votes_total, 2), "vote_pct", votes_for, votes_total,
                      number(item.get("odds")), segment=segment_for(competition, home, away), country=country_for(competition))
            key = _olbg_tip_key(tip)
            if inactive:
                blocked_keys.add(key)
                unique.pop(key, None)
            elif key not in blocked_keys:
                unique.setdefault(key, tip)
        except (ValueError, TypeError, KeyError, OverflowError, OSError):
            continue
    # Hydration is the underlying list, not another page. Include genuine HTML
    # fallback additions without counting the initial display rows twice.
    raw_count = len(public_rows or []) + len(raw_keys - public_raw_keys)
    return list(unique.values()), raw_count, 0


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


def parse_zulubet(html, url, now):
    """Zulubet: probabilidades 1/X/2 publicadas por jogo e hora em UTC (a página converte para a hora local com
    mf_usertime, que soma o fuso do visitante a uma hora UTC). Só conta a dica simples (1, X ou 2) e a
    probabilidade dessa mesma seleção; dicas duplas (1X, X2, 12) ficam de fora."""
    soup = BeautifulSoup(html, "html.parser")
    rows = [tr for tr in soup.select("tr") if len(tr.find_all("td", class_="prediction_full", recursive=False)) == 3
            and tr.select_one('a[href*="match-"]')]
    if not rows:
        raise FetchError("Estrutura Zulubet alterada ou sem jogos publicados")
    result = []
    for row in rows:
        try:
            m = re.search(r"mf_usertime\('(\d{2})/(\d{2})/(\d{4}), (\d{2}):(\d{2})'", str(row))
            if not m:
                continue
            mo, d, y, hh, mm = map(int, m.groups())
            kickoff = datetime(y, mo, d, hh, mm, tzinfo=UTC)
            name = row.select_one('a[href*="match-"]').get_text(" ", strip=True)
            if " - " not in name:
                continue
            home, away = [x.strip() for x in name.split(" - ", 1)]
            probs = [number(td.get_text(strip=True)) for td in row.find_all("td", class_="prediction_full", recursive=False)]
            if any(x is None for x in probs) or abs(sum(probs) - 100) > 3:
                continue
            cells = row.find_all("td", recursive=False)
            tip = next((c.find("b").get_text(strip=True) for c in cells if c.find("b") and c.find("b").get_text(strip=True) in {"1", "X", "2", "1X", "X2", "12"}), "")
            # «-52'» é contagem decrescente para o início; «52'» sem sinal é jogo a decorrer
            live = any(re.fullmatch(r"\d+'", sp.get_text(strip=True)) for sp in row.select("span"))
            order = {"1": ("HOME", 0), "X": ("DRAW", 1), "2": ("AWAY", 2)}
            if tip not in order:
                continue
            outcome, index = order[tip]
            flag = row.select_one("img.flags[title]")
            league = flag["title"].strip() if flag else ""
            odds = [number(td.get_text(strip=True)) for td in row.find_all("td", class_="aver_odds_full", recursive=False)]
            score = cells[-2].get_text(strip=True) if len(cells) >= 2 else ""
            finished = bool(re.fullmatch(r"\d+:\d+", score))
            link = row.select_one('a[href*="match-"]')
            result.append(Tip("zulubet", "football", home, away, kickoff.astimezone(LISBON).date().isoformat(),
                              kickoff.isoformat(), "FT_1X2", outcome, urljoin(url, link["href"]) if link else url,
                              now.isoformat(), league, probs[index], "model_pct",
                              odds=odds[index] if len(odds) == 3 and odds[index] and odds[index] > 1 else None,
                              segment=segment_for(league, home, away),
                              status="finished" if finished else "live" if live else "scheduled", country=country_for(league)))
        except (ValueError, TypeError, KeyError, IndexError):
            continue
    return result, len(rows), 0


def _model_markets(probs):
    """Probabilidades publicadas → mercados (só a seleção com 65%+ conta, como nos outros modelos).
    probs: dict com o25/o15/o35 (mais de X golos) e bts/ots (ambas marcam sim/não)."""
    out = []
    for line, key in (("1.5", "o15"), ("2.5", "o25"), ("3.5", "o35")):
        p = probs.get(key)
        if p is None:
            continue
        out.append((f"FT_TOTAL_{line}", "OVER", p) if p >= 50 else (f"FT_TOTAL_{line}", "UNDER", 100 - p))
    if probs.get("bts") is not None and probs.get("ots") is not None:
        out.append(("FT_BTTS", "YES", probs["bts"]) if probs["bts"] >= probs["ots"] else ("FT_BTTS", "NO", probs["ots"]))
    return out


def parse_statarea(html, url, now):
    """Statarea (versão leve): modelo próprio com % de 1/X/2, golos e ambas marcam. A hora da página segue o fuso
    de quem pede (varia com o servidor do GitHub), por isso NÃO se usa: a Statarea só confirma jogos que outra fonte
    já tem com hora verificada. O dia vem do próprio URL."""
    m = re.search(r"/prediction/(\d{4}-\d{2}-\d{2})/", url)
    if not m:
        raise FetchError("URL Statarea sem data")
    day = m.group(1)
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select("tr")
    if not any("prediction:" in r.get_text() for r in rows):
        raise FetchError("Estrutura Statarea alterada ou sem jogos publicados")
    result, league, pred, teams, raw = [], "", None, [], 0
    for tr in rows:
        cells = tr.find_all("td", recursive=False)
        text = tr.get_text(" ", strip=True)
        if len(cells) == 2 and cells[0].find("img") and not text.startswith(("time:", "prediction:")):
            league, pred, teams = text, None, []
        elif text.startswith("prediction:"):
            b = tr.find("b"); pred, teams = (b.get_text(strip=True) if b else ""), []
        elif len(cells) == 2 and pred is not None and len(teams) < 2 and not text.startswith("time:"):
            teams.append((cells[0].get_text(" ", strip=True), cells[1].get_text(strip=True)))
        elif len(cells) == 11 and len(teams) == 2 and all("%" in c.get_text() for c in cells):
            raw += 1
            vals = [number(c.get_text(strip=True)) for c in cells]
            (home, s1), (away, s2) = teams
            teams, p = [], pred
            pred = None
            if None in vals or not home or not away or re.fullmatch(r"\d+", s1 or "") or re.fullmatch(r"\d+", s2 or ""):
                continue  # jogo já com resultado, ou linha incompleta
            comp = league.replace("-", " ")
            base = dict(segment=segment_for(comp, home, away), country=country_for(comp))
            picks = []
            order = {"1": ("HOME", 0), "X": ("DRAW", 1), "2": ("AWAY", 2)}
            if p in order and abs(sum(vals[:3]) - 100) <= 3:
                picks.append(("FT_1X2", order[p][0], vals[order[p][1]]))
            picks += _model_markets({"o15": vals[6], "o25": vals[7], "o35": vals[8], "bts": vals[9], "ots": vals[10]})
            for market, outcome, metric in picks:
                result.append(Tip("statarea", "football", home, away, day, None, market, outcome, url, now.isoformat(),
                                  comp, metric, "model_pct", **base))
    return result, raw, 0


def parse_vitibet(html, url, now):
    """Vitibet: modelo próprio checo com % de 1/X/2 e resultado provável. Sem hora: só confirma jogos que outra
    fonte já tem com hora verificada. Dicas duplas (10, 02, 12) não contam."""
    soup = BeautifulSoup(html, "html.parser")
    rows = [tr for tr in soup.select("tr") if len(tr.select("td.standardbunkaprocenta")) >= 3]
    if not rows:
        raise FetchError("Estrutura Vitibet alterada ou sem jogos publicados")
    result, league = [], ""
    for tr in soup.select("tr"):
        if "odseknutiligy" in (tr.get("class") or []):
            league = tr.get_text(" ", strip=True)
            continue
        cells = tr.find_all("td", recursive=False)
        pcts = tr.select("td.standardbunkaprocenta")
        if len(pcts) < 3 or len(cells) < 12:
            continue
        try:
            dm = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.?", cells[0].get_text(strip=True))
            if not dm:
                continue
            d, mo = int(dm[1]), int(dm[2])
            local = now.astimezone(LISBON)
            year = local.year + (1 if mo == 1 and local.month == 12 else -1 if mo == 12 and local.month == 1 else 0)
            day = f"{year:04d}-{mo:02d}-{d:02d}"
            home, away = cells[2].get_text(" ", strip=True), cells[3].get_text(" ", strip=True)
            probs = [number(x.get_text(strip=True)) for x in pcts[:3]]
            tipcell = tr.find("td", class_=re.compile(r"^barvapodtipek"))
            tip = tipcell.get_text(strip=True) if tipcell else ""
            order = {"1": ("HOME", 0), "0": ("DRAW", 1), "2": ("AWAY", 2)}
            if tip not in order or None in probs or abs(sum(probs) - 100) > 3 or not home or not away:
                continue
            outcome, index = order[tip]
            link = tr.select_one('a[href*="match-detail"]')
            result.append(Tip("vitibet", "football", home, away, day, None, "FT_1X2", outcome,
                              urljoin(url, link["href"]) if link else url, now.isoformat(), league, probs[index],
                              "model_pct", segment=segment_for(league, home, away), country=country_for(league)))
        except (ValueError, TypeError, KeyError, IndexError):
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
             ("predictz", "https://www.predictz.com/predictions/", parse_predictz, {}),
             ("zulubet", "https://www.zulubet.com/", parse_zulubet, {}),
             ("vitibet", "https://www.vitibet.com/index.php?clanek=quicktips&sekce=fotbal&lang=en&design_version=old", parse_vitibet, {}),
             ("statarea", "https://www.statarea.com/olddevices/prediction/" + now.astimezone(LISBON).date().isoformat() + "/", parse_statarea, {})]
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
    for source, name in [("olbg", "OLBG"), ("forebet", "Forebet"), ("protipster", "ProTipster"), ("predictz", "PredictZ"), ("zulubet", "Zulubet"),
                         ("vitibet", "Vitibet"), ("statarea", "Statarea")]:
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
    try:
        from .extra_predictions import collect_betclan
        data, status = collect_betclan(client, datetime.now(UTC), tips)
        tips.extend(data)
        sources.append(status)
    except Exception as exc:
        sources.append({"id": "betclan", "name": "BetClan", "status": "error", "collected": 0,
                        "message": str(exc) if isinstance(exc, FetchError) else "Falha do adaptador BetClan"})
    return tips, sources
