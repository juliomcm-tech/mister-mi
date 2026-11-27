"""Resultados finais a partir de fontes públicas gratuitas, para conferir o boletim de cada dia.

ESPN (scoreboard público) para futebol, basquetebol, hóquei, futebol americano e ténis; Zulubet (resultados
publicados na página do dia) como segunda fonte para futebol. São provas de resultado, nunca votos de previsão.

Regras de prudência (iguais ao resto do Mister Mi):
- só placares finais; futebol e hóquei com mercados de 90/60 minutos não usam resultados com prolongamento,
  a menos que o placar do tempo regulamentar venha explícito (períodos do hóquei);
- jogo adiado, cancelado ou abandonado fica «devolvido» só 48 h depois da hora marcada;
- cada recurso é pedido no máximo de 3 em 3 horas (30 min depois de uma falha) e há um limite por corrida.
"""
from __future__ import annotations

from datetime import datetime, timedelta
import json
import re

from bs4 import BeautifulSoup

from .core import LISBON, UTC, iso_time, team_equal
from .sources import Client, FetchError

ESPN = "https://site.api.espn.com/apis/site/v2/sports/{path}/scoreboard?dates={day}"
ZULU = "https://www.zulubet.com/tips-{day}.html"
MAX_RESOURCES = 14
FINAL = {"STATUS_FINAL", "STATUS_FULL_TIME", "STATUS_FINAL_OT", "STATUS_FINAL_SO", "STATUS_FINAL_AET", "STATUS_FINAL_PEN",
         "STATUS_END_OF_EXTRATIME"}
EXTRA = {"STATUS_FINAL_AET", "STATUS_FINAL_PEN", "STATUS_END_OF_EXTRATIME", "STATUS_FINAL_OT", "STATUS_FINAL_SO"}
VOID = {"STATUS_POSTPONED", "STATUS_CANCELED", "STATUS_ABANDONED", "STATUS_FORFEIT", "STATUS_SUSPENDED"}


def espn_paths(record: dict) -> list[str]:
    sport, comp = record.get("sport"), str(record.get("competition", "")).lower()
    if sport == "football":
        return ["soccer/all"]
    if sport == "basketball":
        if "euroleague" in comp:
            return ["basketball/euroleague"]
        if "wnba" in comp:
            return ["basketball/wnba"]
        if "ncaa" in comp or "college" in comp:
            return ["basketball/mens-college-basketball"]
        return ["basketball/nba"] if "nba" in comp or not comp else []
    if sport == "hockey":
        return ["hockey/nhl"] if "nhl" in comp or not comp else []
    if sport == "american_football":
        return ["football/college-football"] if "ncaa" in comp or "college" in comp else ["football/nfl"]
    if sport == "tennis":
        women = "wta" in comp or "women" in comp or ":w" in str(record.get("segment", ""))
        return ["tennis/wta"] if women else ["tennis/atp", "tennis/wta"] if "atp" not in comp else ["tennis/atp"]
    return []


def _names(competitor: dict) -> list[str]:
    who = competitor.get("team") or competitor.get("athlete") or {}
    return [x for x in (who.get("displayName"), who.get("shortDisplayName"), who.get("name"), who.get("location") and
                        who.get("name") and f"{who.get('location')} {who.get('name')}") if isinstance(x, str) and x]


def _int(value):
    try:
        n = int(float(value))
        return n if 0 <= n <= 300 else None
    except (TypeError, ValueError):
        return None


def parse_espn(data: dict, sport: str) -> list[dict]:
    """Normaliza o scoreboard: [{home:[nomes], away:[nomes], date, state, hs, as, reg}]"""
    games = []
    for event in data.get("events", []) if isinstance(data, dict) else []:
        comps = []
        if sport == "tennis":
            for grouping in event.get("groupings", []) or []:
                slug = str((grouping.get("grouping") or {}).get("slug", ""))
                if "double" in slug or "mixed" in slug:
                    continue
                comps += grouping.get("competitions", []) or []
            comps += event.get("competitions", []) if not comps else []
        else:
            comps = (event.get("competitions") or [])[:1]
        for comp in comps:
            try:
                status = (comp.get("status") or event.get("status") or {}).get("type", {})
                name = status.get("name", "")
                cs = comp.get("competitors") or []
                if len(cs) != 2:
                    continue
                if sport == "tennis":
                    home, away = cs[0], cs[1]
                else:
                    home = next(c for c in cs if c.get("homeAway") == "home")
                    away = next(c for c in cs if c.get("homeAway") == "away")
                game = {"home": _names(home), "away": _names(away), "date": comp.get("date") or event.get("date"),
                        "state": name, "id": str(comp.get("id") or event.get("id") or "")}
                if sport == "tennis":
                    if home.get("winner") is True or away.get("winner") is True:
                        game.update(hs=1 if home.get("winner") is True else 0, as_=1 if away.get("winner") is True else 0)
                else:
                    game.update(hs=_int(home.get("score")), as_=_int(away.get("score")))
                    if sport == "hockey":
                        lh, la = home.get("linescores") or [], away.get("linescores") or []
                        if len(lh) >= 3 and len(la) >= 3:
                            rh = [_int((x or {}).get("value")) for x in lh[:3]]
                            ra = [_int((x or {}).get("value")) for x in la[:3]]
                            if None not in rh and None not in ra:
                                game["reg"] = (sum(rh), sum(ra))
                games.append(game)
            except (StopIteration, AttributeError, TypeError):
                continue
    return games


def parse_zulubet_scores(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    games = []
    for row in soup.select("tr"):
        if len(row.find_all("td", class_="prediction_full", recursive=False)) != 3:
            continue
        m = re.search(r"mf_usertime\('(\d{2})/(\d{2})/(\d{4}), (\d{2}):(\d{2})'", str(row))
        cells = row.find_all("td", recursive=False)
        if not m or len(cells) < 2:
            continue
        link = row.select_one('a[href*="match-"]')
        label = (link or cells[1]).get_text(" ", strip=True)
        if " - " not in label:
            continue
        score = re.fullmatch(r"(\d{1,2}):(\d{1,2})", cells[-2].get_text(strip=True))
        if not score:
            continue
        mo, d, y, hh, mm = map(int, m.groups())
        home, away = [x.strip() for x in label.split(" - ", 1)]
        games.append({"home": [home], "away": [away], "date": datetime(y, mo, d, hh, mm, tzinfo=UTC).isoformat(),
                      "state": "STATUS_FULL_TIME", "hs": int(score[1]), "as_": int(score[2]),
                      "id": link["href"].rsplit("-", 1)[-1].split(".")[0] if link else ""})
    return games


def _orient(record: dict, game: dict, sport: str) -> dict | None:
    """Devolve o jogo virado para a ordem do registo (no ténis a ordem dos jogadores pode vir trocada)."""
    if _same(record, game, sport):
        return game
    if sport == "tennis":
        flipped = {**game, "home": game["away"], "away": game["home"], "hs": game.get("as_"), "as_": game.get("hs")}
        if _same(record, flipped, sport):
            return flipped
    return None


def _same(record: dict, game: dict, sport: str) -> bool:
    try:
        if not game.get("date"):
            return False
        gap = abs((iso_time(record["kickoff"]) - iso_time(game["date"])).total_seconds())
        if gap > (4 * 3600 if sport == "tennis" else 35 * 60):
            return False
        if sport == "tennis" and iso_time(record["kickoff"]).astimezone(LISBON).date() != iso_time(game["date"]).astimezone(LISBON).date():
            return False
        return (any(team_equal(record["home"], n, sport) for n in game["home"])
                and any(team_equal(record["away"], n, sport) for n in game["away"]))
    except (KeyError, TypeError, ValueError):
        return False


def _result(record: dict, game: dict, now: datetime, source: str, url: str) -> dict | None:
    sport, state, market = record["sport"], game.get("state", ""), record.get("market", "")
    base = {"id": record["id"], "source": source, "source_url": url, "source_event_id": game.get("id", ""),
            "verified_at": now.isoformat()}
    if state in VOID:
        return {**base, "status": "void"} if now > iso_time(record["kickoff"]) + timedelta(hours=48) else None
    if state not in FINAL:
        return None
    hs, as_ = game.get("hs"), game.get("as_")
    if sport == "hockey" and market == "FT_1X2":
        if state in EXTRA or "reg" in game:
            if "reg" not in game:
                return None
            hs, as_ = game["reg"]
    elif sport == "football" and state in EXTRA:
        return None  # 90 minutos não confirmados (prolongamento/penáltis)
    if hs is None or as_ is None:
        return None
    return {**base, "status": "final", "home_score": hs, "away_score": as_}


def collect_public_results(history: dict, now: datetime) -> tuple[list[dict], list[dict]]:
    now = now.astimezone(UTC)
    pending = []
    for r in history.get("records", []) if isinstance(history.get("records"), list) else []:
        try:
            if r.get("result") != "pending" or not r.get("id"):
                continue
            k = iso_time(r["kickoff"])
            wait = {"football": 2.2, "tennis": 3.5, "basketball": 2.8, "hockey": 2.8, "american_football": 3.8}.get(r.get("sport"), 3)
            if now < k + timedelta(hours=wait) or now > k + timedelta(days=21):
                continue
            pending.append(r)
        except (KeyError, TypeError, ValueError):
            continue
    previous = {s.get("resource"): s for s in history.get("result_sources", []) or []
                if isinstance(s, dict) and s.get("id") in {"espn", "zulubet_results"}}
    wanted: dict[tuple[str, str, str], list[dict]] = {}
    for r in pending:
        k = iso_time(r["kickoff"])
        for path in espn_paths(r):
            for day in {(k - timedelta(hours=6)).strftime("%Y%m%d"), (k + timedelta(hours=6)).strftime("%Y%m%d"), k.strftime("%Y%m%d")}:
                wanted.setdefault(("espn", path, day), []).append(r)
        if r.get("sport") == "football":
            wanted.setdefault(("zulubet_results", "football", k.strftime("%d-%m-%Y")), []).append(r)
    client = Client()
    results, statuses, done = [], [], set()
    for (kind, path, day), records in sorted(wanted.items(), key=lambda x: x[0][2], reverse=True):
        records = [r for r in records if r["id"] not in done]
        resource = f"{path}/{day}" if kind == "espn" else f"zulubet/{day}"
        old = previous.get(resource, {})
        try:
            if old.get("next_check_at") and iso_time(old["next_check_at"]) > now:
                statuses.append({**old, "status": "cached"})
                continue
        except (TypeError, ValueError):
            pass
        if not records:
            continue
        if len([s for s in statuses if s.get("status") != "cached"]) >= MAX_RESOURCES:
            break
        url = ESPN.format(path=path, day=day) if kind == "espn" else ZULU.format(day=day)
        status = {"id": kind, "name": "ESPN" if kind == "espn" else "Zulubet (resultados)", "resource": resource,
                  "checked_at": now.isoformat(), "collected": 0}
        try:
            if kind == "espn":
                sport = records[0]["sport"]
                games = parse_espn(json.loads(client.get(url, check_robots=False)), sport)
            else:
                games = parse_zulubet_scores(client.get(url))
            for r in records:
                found = [o for o in (_orient(r, g, r["sport"]) for g in games) if o]
                if len(found) != 1:
                    continue
                res = _result(r, found[0], now, kind, url)
                if res:
                    results.append(res)
                    done.add(r["id"])
                    status["collected"] += 1
            status.update(status="ok", next_check_at=(now + timedelta(hours=3)).isoformat())
        except Exception as exc:
            status.update(status="error", message=str(exc) if isinstance(exc, FetchError) else type(exc).__name__,
                          next_check_at=(now + timedelta(minutes=30)).isoformat())
        statuses.append(status)
    return results, statuses
