"""Bounded public BetClan corroboration. FAQ explicitly permits prediction sharing.

Index fixtures are a search catalog, not analyzed predictions. Details are read
only for a bounded set of matches already seen in the other prediction feeds.
The model block is separate from Users Average. No site JavaScript is executed.
"""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.parse import urlparse, urljoin, quote, urlsplit, urlunsplit
import json
import re

from bs4 import BeautifulSoup
from .core import Tip, DEFAULTS, UTC, LISBON, iso_time, name_key, team_equal

HOST = "www.betclan.com"
SPORT_PATHS = {"football": "football", "tennis": "tennis", "basketball": "basketball",
               "ice-hockey": "hockey", "american-football": "american_football"}
INDEX_URLS = [f"https://{HOST}/todays-{slug}-predictions/" for slug in SPORT_PATHS]
INDEX_PATH = re.compile(r"^/(?:todays|tomorrows|day-after-tomorrows)-(?:football|tennis|basketball|ice-hockey|american-football)-predictions/$")


def safe_url(value):
    if not isinstance(value, str):
        raise ValueError("URL BetClan inválido")
    parsed = urlsplit(urljoin(f"https://{HOST}/", value))
    if parsed.scheme != "https" or parsed.netloc != HOST or parsed.query or parsed.fragment:
        raise ValueError("URL fora do âmbito BetClan")
    return urlunsplit((parsed.scheme, parsed.netloc, quote(parsed.path, safe="/%-._~"), "", ""))


def public_json(soup):
    for script in soup.select('script[type="application/ld+json"]'):
        raw = script.get_text().strip()
        try:
            data, end = json.JSONDecoder().raw_decode(raw)
            # The public index template appends one surplus closing brace.
            # Accept only that observed typo; never arbitrary trailing scripts.
            if raw[end:].strip() not in {"", "}"}:
                continue
        except (ValueError, RecursionError):
            continue
        values = data if isinstance(data, list) else [data]
        for item in values:
            if isinstance(item, dict):
                yield item
                for child in item.get("@graph", []):
                    if isinstance(child, dict):
                        yield child


@dataclass(frozen=True)
class Fixture:
    sport: str
    home: str
    away: str
    kickoff: str
    date: str
    url: str
    competition: str


def parse_index(html, url):
    path = urlparse(safe_url(url)).path
    slug = next((s for s in SPORT_PATHS if path.endswith(f"-{s}-predictions/")), None)
    if slug is None or not INDEX_PATH.fullmatch(path):
        raise ValueError("Índice BetClan fora do âmbito")
    sport = SPORT_PATHS[slug]
    soup = BeautifulSoup(html, "html.parser")
    rows, links = {}, set()
    for node in soup.select('a[href]'):
        try:
            link = safe_url(node["href"])
            if INDEX_PATH.fullmatch(urlparse(link).path):
                links.add(link)
        except ValueError:
            pass
    for item in public_json(soup):
        if item.get("@type") == "SiteNavigationElement":
            try:
                link = safe_url(item.get("url"))
                if INDEX_PATH.fullmatch(urlparse(link).path):
                    links.add(link)
            except ValueError:
                pass
        if item.get("@type") != "SportsEvent":
            continue
        try:
            link = safe_url(item["url"])
            if "/predictionsdetails/" not in urlparse(link).path:
                continue
            kickoff = iso_time(item["startDate"])
            home, away = item["homeTeam"]["name"], item["awayTeam"]["name"]
            if not all(isinstance(n, str) and n.strip() for n in (home, away)):
                continue
            if item.get("eventStatus", "https://schema.org/EventScheduled").rsplit("/", 1)[-1] != "EventScheduled":
                continue
            competition = item.get("location", {}).get("name", "")
            if not isinstance(competition, str):
                competition = ""
            rows[link] = Fixture(sport, home.strip(), away.strip(), kickoff.isoformat(),
                                 kickoff.astimezone(LISBON).date().isoformat(), link, competition)
        except (ValueError, TypeError, KeyError, AttributeError):
            continue
    return list(rows.values()), links


def parse_detail(html, fixture, now):
    from .sources import market_selection, segment_for, country_for
    soup = BeautifulSoup(html, "html.parser")
    events = [item for item in public_json(soup) if item.get("@type") == "SportsEvent"]
    if len(events) != 1:
        return []
    event = events[0]
    try:
        if safe_url(event["url"]) != fixture.url:
            return []
        if event.get("eventStatus", "").rsplit("/", 1)[-1] != "EventScheduled":
            return []
        home, away = event["homeTeam"]["name"], event["awayTeam"]["name"]
        if not team_equal(home, fixture.home, fixture.sport) or not team_equal(away, fixture.away, fixture.sport):
            return []
        detail_time = iso_time(event["startDate"])
        if detail_time.astimezone(LISBON).date().isoformat() != fixture.date:
            return []
        # Detail and index have contradictory UTC offsets on some football pages.
        # Preserve the date, but never use that source as a timed anchor then.
        kickoff = fixture.kickoff if abs((detail_time - iso_time(fixture.kickoff)).total_seconds()) <= 1200 else None
    except (ValueError, TypeError, KeyError):
        return []
    block = soup.select_one(".partone")
    if not block:
        return []
    result = []
    for heading in block.select("h4"):
        label = heading.get_text(" ", strip=True)
        selected = heading.find_next_sibling("h5")
        stats = heading.find_next_sibling("div", class_="vote__stats")
        if not selected or not stats:
            continue
        # A group must end before the next market heading.
        if stats.find_previous_sibling("h4") is not heading:
            continue
        selection = selected.get_text(" ", strip=True)
        if name_key(label) == "winner":
            label = "Full Time Result" if fixture.sport == "football" else "Match Winner"
        market = market_selection(label, selection, fixture.home, fixture.away, fixture.sport)
        if not market:
            continue
        probabilities, metric = [], None
        for section in stats.select(".cell__section"):
            name = section.select_one(".vote__count")
            pct = section.select_one(".vote__pct")
            if not name or not pct or not re.fullmatch(r"\s*\d+(?:\.\d+)?\s*%\s*", pct.get_text()):
                probabilities = []
                break
            value = float(pct.get_text().strip().rstrip("%"))
            if not 0 <= value <= 100:
                probabilities = []
                break
            probabilities.append(value)
            candidate = market_selection(label, name.get_text(" ", strip=True), fixture.home, fixture.away, fixture.sport)
            if candidate == market:
                metric = value
        if metric is None or len(probabilities) not in {2, 3} or abs(sum(probabilities) - 100) > 2:
            continue
        if fixture.sport == "hockey":
            if len(probabilities) != 3:
                continue  # No explicit overtime scope: two-way hockey is ambiguous.
            market = ("FT_1X2", market[1])
        result.append(Tip("betclan", fixture.sport, fixture.home, fixture.away, fixture.date, kickoff,
                          *market, fixture.url, now.isoformat(), fixture.competition, metric, "model_pct",
                          segment=segment_for(fixture.competition, fixture.home, fixture.away),
                          country=country_for(fixture.competition)))
    return result


def collect_betclan(client, now, candidates, settings=None, max_details=24):
    settings = DEFAULTS | (settings or {})
    today = now.astimezone(LISBON).date()
    end = (today + timedelta(days=2)).isoformat()
    pages, fixtures, discovered = [], {}, set()

    def read(url):
        try:
            rows, links = parse_index(client.get(url), url)
            return rows, links, {"url": url, "status": "ok", "indexed_fixtures": len(rows)}
        except Exception as exc:
            from .sources import FetchError
            return [], set(), {"url": url, "status": "error", "message": str(exc) if isinstance(exc, FetchError) else "Índice BetClan inválido"}

    def batch(urls):
        with ThreadPoolExecutor(max_workers=4) as pool:
            for rows, links, log in pool.map(read, urls):
                fixtures.update({r.url: r for r in rows})
                discovered.update(links)
                pages.append(log)
    batch(INDEX_URLS)
    extra = sorted(url for url in discovered if url not in INDEX_URLS
                   and ("/tomorrows-" in url or "/day-after-tomorrows-football-" in url))[:6]
    batch(extra)
    scheduled = [f for f in fixtures.values() if today.isoformat() <= f.date <= end
                 and (iso_time(f.kickoff) - now).total_seconds() > settings["lead_minutes"] * 60]
    requests = []
    for f in scheduled:
        matching = [t for t in candidates if t.kickoff and t.status == "scheduled" and t.sport == f.sport and t.event_date == f.date
                    and team_equal(t.home, f.home, f.sport) and team_equal(t.away, f.away, f.sport)
                    and abs((iso_time(t.kickoff) - iso_time(f.kickoff)).total_seconds()) <= 1200]
        if not matching:
            continue
        priority = 0 if any(t.eligible(settings) for t in matching) else 1
        volume = max((t.votes_total for t in matching), default=0)
        # Unknown two-way hockey scope must not consume the exploration budget
        # ahead of sports whose published winner market can be normalized.
        requests.append((priority, int(f.sport == "hockey"), f.date, -volume, f.kickoff, f))
    requests.sort(key=lambda row: row[:-1])
    selected = [row[-1] for row in requests[:max(0, min(30, int(max_details)))]]

    def detail(f):
        try:
            data = parse_detail(client.get(f.url), f, datetime.now(UTC))
            return data, {"url": f.url, "status": "ok" if data else "partial", "collected": len(data)}
        except Exception as exc:
            from .sources import FetchError
            return [], {"url": f.url, "status": "error", "message": str(exc) if isinstance(exc, FetchError) else "Detalhe BetClan inválido", "collected": 0}
    tips = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for data, log in pool.map(detail, selected):
            tips.extend(data)
            pages.append(log)
    dates = sorted({f.date for f in scheduled})
    status = "error" if not any(p["status"] == "ok" for p in pages) else "partial" if any(p["status"] != "ok" for p in pages) else "ok"
    return tips, {"id": "betclan", "name": "BetClan", "status": status, "collected": len(tips),
                  "raw_rows": len(fixtures), "details_requested": len(selected), "detail_limit": max_details,
                  "indexed_by_date": [{"date": day, "fixtures": sum(f.date == day for f in scheduled)} for day in dates],
                  "indexed_by_sport_date": [{"date": day, "sport": sport, "fixtures": sum(f.date == day and f.sport == sport for f in scheduled)}
                                             for day in dates for sport in SPORT_PATHS.values()],
                  "message": f"{len(fixtures)} eventos indexados; {len(selected)} detalhes consultados para cruzar com outros feeds. Índice não equivale a previsões analisadas.",
                  "pages": pages}
