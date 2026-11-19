"""A bounded, independently licensed calendar; never a prediction provider.

Only community-maintained Bundesliga 1/2 data is enabled. Persist the returned
object between runs to honour its per-resource six-hour cache and error backoff.
"""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timedelta
import json
import re

from .core import LISBON, UTC, identity_tags, iso_time, name_key, team_equal
from .sources import Client, FetchError

BASE_URL = "https://api.openligadb.de/getmatchdata/"
ATTRIBUTION = "Data from OpenLigaDB (www.openligadb.de), licensed under ODbL 1.0"
LICENSE_URL = "https://www.openligadb.de/en/license"
LEAGUES = {"bl1": "Bundesliga 1", "bl2": "Bundesliga 2"}
_ALIASES = {
    "bayern munich": "fc bayern munchen", "bayern munchen": "fc bayern munchen",
    "cologne": "1 fc koln", "fc cologne": "1 fc koln", "koln": "1 fc koln",
    "leverkusen": "bayer 04 leverkusen", "bayer leverkusen": "bayer 04 leverkusen",
    "paderborn": "sc paderborn 07", "frankfurt": "eintracht frankfurt",
    "hoffenheim": "tsg hoffenheim", "union berlin": "1 fc union berlin",
    "leipzig": "rb leipzig", "mgladbach": "borussia monchengladbach",
    "borussia m gladbach": "borussia monchengladbach", "dortmund": "borussia dortmund",
    "elversberg": "sv 07 elversberg", "freiburg": "sc freiburg",
    "sport club freiburg": "sc freiburg", "schalke": "fc schalke 04",
    "schalke 04": "fc schalke 04", "stuttgart": "vfb stuttgart",
    "augsburg": "fc augsburg", "mainz": "1 fsv mainz 05", "mainz 05": "1 fsv mainz 05",
    "werder bremen": "sv werder bremen", "hamburg": "hamburger sv",
    "darmstadt": "sv darmstadt 98", "darmstadt 98": "sv darmstadt 98",
    "heidenheim": "1 fc heidenheim 1846", "arminia bielefeld": "dsc arminia bielefeld",
    "bielefeld": "dsc arminia bielefeld", "magdeburg": "1 fc magdeburg",
    "wolfsburg": "vfl wolfsburg", "kiel": "holstein kiel", "hannover": "hannover 96",
    "greuther furth": "spvgg greuther furth", "nurnberg": "1 fc nurnberg",
    "nuremberg": "1 fc nurnberg", "braunschweig": "eintracht braunschweig",
    "st pauli": "fc st pauli", "bochum": "vfl bochum",
}


def canonical_team(value: str) -> str:
    key = name_key(value)
    return _ALIASES.get(key, key)


def league_for(record: dict) -> str | None:
    if record.get("sport") != "football" or record.get("country") != "Germany":
        return None
    competition = record.get("competition")
    if not isinstance(competition, str):
        return None
    key = re.sub(r"^(?:germany|german)\s+", "", name_key(competition))
    key = re.sub(r"\s+20\d{2}(?:\s+20\d{2})?$", "", key).strip()
    if key in {"bundesliga", "1 bundesliga", "bundesliga 1", "bundesliga i"}:
        return "bl1"
    if key in {"2 bundesliga", "bundesliga 2", "bundesliga ii"}:
        return "bl2"
    return None


def _normalise(data, league, season):
    if not isinstance(data, list) or len(data) > 1000:
        raise FetchError("Formato de calendário OpenLigaDB inesperado")
    unique, conflicts = {}, set()
    for row in data:
        try:
            if not isinstance(row, dict) or row.get("leagueShortcut") != league or row.get("leagueSeason") != season:
                continue
            if (any(row.get(flag) for flag in ("cancelled", "postponed", "matchIsCancelled", "matchIsPostponed"))
                    or str(row.get("status", "")).lower() in {"cancelled", "postponed", "abandoned", "suspended"}):
                continue
            if type(row.get("matchIsFinished")) is not bool:
                continue
            event_id = row["matchID"]
            if type(event_id) is not int or event_id <= 0:
                continue
            kickoff = iso_time(row["matchDateTimeUTC"])
            home, away = row["team1"]["teamName"], row["team2"]["teamName"]
            if not all(isinstance(name, str) and name.strip() for name in (home, away)):
                continue
            if canonical_team(home) == canonical_team(away) or identity_tags(home) or identity_tags(away):
                continue
            item = {"source": "openligadb", "source_event_id": str(event_id), "league": league,
                    "season": season, "sport": "football", "country": "Germany", "segment": "open",
                    "competition": LEAGUES[league], "home": home.strip(), "away": away.strip(),
                    "date": kickoff.astimezone(LISBON).date().isoformat(), "kickoff": kickoff.isoformat(),
                    "provider_finished": row["matchIsFinished"], "source_url": BASE_URL + f"{league}/{season}",
                    "attribution": ATTRIBUTION, "license": "ODbL-1.0", "license_url": LICENSE_URL,
                    "counts_as_prediction": False}
            if event_id in unique and item != unique[event_id]:
                conflicts.add(event_id)
            else:
                unique[event_id] = item
        except (KeyError, ValueError, TypeError, OverflowError):
            continue
    return [item for event_id, item in unique.items() if event_id not in conflicts]


def collect_fixture_catalog(previous: dict | None, now: datetime, *, client=None) -> dict:
    """Fetch at most two season resources; expose current-day through day+2 fixtures.

    ``resources`` retains a seven-day normalized cache and timestamps for the
    next run. Cached entries are not re-stamped as newly verified data. Request
    failures back off from 30 minutes to six hours; no immediate retries occur.
    """
    if now.tzinfo is None:
        raise ValueError("now must contain a time zone")
    now = now.astimezone(UTC)
    today = now.astimezone(LISBON).date()
    end = today + timedelta(days=2)
    season = today.year if today.month >= 7 else today.year - 1
    previous = previous if isinstance(previous, dict) else {}
    old_resources = previous.get("resources", [])
    prior = {row.get("resource"): row for row in old_resources if isinstance(row, dict)} if isinstance(old_resources, list) else {}
    client = client or Client()
    resources, fixtures = [], []
    for league in LEAGUES:
        resource = f"{league}/{season}"
        url = BASE_URL + resource
        old = prior.get(resource, {})
        cached = False
        try:
            checked = iso_time(old["checked_at"])
            due = iso_time(old["next_check_at"])
            cache_covers = old.get("cache_from", "9999") <= today.isoformat() and old.get("cache_through", "") >= end.isoformat()
            cached_rows = old.get("fixtures")
            valid_cache = isinstance(cached_rows, list) and len(cached_rows) <= 1000
            if valid_cache:
                for row in cached_rows:
                    if (not isinstance(row, dict) or row.get("league") != league or row.get("season") != season
                            or type(row.get("provider_finished")) is not bool
                            or row.get("date") != iso_time(row["kickoff"]).astimezone(LISBON).date().isoformat()
                            or not all(isinstance(row.get(key), str) and row[key] for key in ("home", "away", "source_event_id"))):
                        valid_cache = False
                        break
            cached = (-60 <= (now - checked).total_seconds() and due > now
                      and (old.get("status") == "error" or cache_covers and valid_cache))
        except (ValueError, TypeError, KeyError):
            pass
        if cached:
            status = {**old, "status": "error" if old.get("status") == "error" else "cached"}
        else:
            status = {"id": "openligadb_calendar", "resource": resource, "league": league, "season": season,
                      "url": url, "checked_at": now.isoformat(), "attribution": ATTRIBUTION,
                      "license": "ODbL-1.0", "license_url": LICENSE_URL, "counts_as_prediction": False}
            try:
                rows = _normalise(json.loads(client.get(url, check_robots=False)), league, season)
                if not rows:
                    raise FetchError("Calendário de época vazio; cobertura não confirmada")
                through = (today + timedelta(days=7)).isoformat()
                rows = [row for row in rows if today.isoformat() <= row["date"] <= through]
                status.update(status="ok", next_check_at=(now + timedelta(hours=6)).isoformat(),
                              cache_from=today.isoformat(), cache_through=through, fixtures=rows, failures=0)
            except Exception as exc:
                try:
                    failures = min(5, max(0, int(old.get("failures", 0))) + 1)
                except (ValueError, TypeError, OverflowError):
                    failures = 1
                status.update(status="error", next_check_at=(now + timedelta(minutes=min(360, 30 * 2 ** (failures - 1)))).isoformat(),
                              fixtures=[], failures=failures,
                              message=str(exc) if isinstance(exc, FetchError) else "Calendário indisponível ou inválido")
        resources.append(status)
        if status["status"] not in {"ok", "cached"}:
            continue
        for row in status.get("fixtures", []):
            if today.isoformat() <= row["date"] <= end.isoformat():
                state = "finished" if row["provider_finished"] else "scheduled" if iso_time(row["kickoff"]) > now else "started_unconfirmed"
                fixtures.append({**row, "status": state, "checked_at": status["checked_at"], "cache_status": status["status"]})
    states = {resource["status"] for resource in resources}
    status = "error" if states == {"error"} else "partial" if "error" in states else "cached" if states == {"cached"} else "ok"
    counts = [{"date": (today + timedelta(days=offset)).isoformat(),
               "scheduled": None if status == "error" else sum(row["date"] == (today + timedelta(days=offset)).isoformat() and row["status"] == "scheduled" for row in fixtures),
               "coverage": "unavailable" if status == "error" else "partial" if status == "partial" else "configured_resources_only"}
              for offset in (0, 1, 2)]
    return {"id": "openligadb_calendar", "kind": "fixture_calendar", "status": status,
            "generated_at": now.isoformat(), "window_from": today.isoformat(), "window_through": end.isoformat(),
            "scope": "Futebol masculino · Alemanha · Bundesliga 1 e 2", "complete_global_coverage": False,
            "counts_as_prediction": False, "attribution": ATTRIBUTION, "license": "ODbL-1.0", "license_url": LICENSE_URL,
            "resources": resources, "fixtures": sorted(fixtures, key=lambda row: (row["kickoff"], row["source_event_id"])),
            "counts_by_date": counts, "complete_within_configured_resources": "error" not in states}


def verify_fixture(record, catalog: dict, *, tolerance_minutes=20) -> dict:
    """Check date, both participant identities, league and kickoff; add no vote.

    ``not_found`` and ``out_of_scope`` are not proof that a fixture is false:
    OpenLigaDB is selective community data. Only a uniquely identified fixture
    with a contradictory scheduled time can return ``conflict``.
    """
    record = asdict(record) if is_dataclass(record) else record
    base = {"source": "openligadb_calendar", "counts_as_prediction": False}
    if not isinstance(record, dict):
        return {**base, "status": "unverified"}
    if not all(isinstance(record.get(key), str) and record[key] for key in ("home", "away")):
        return {**base, "status": "unverified"}
    league = league_for(record)
    segment = record.get("segment", "open")
    if league is None or segment != "open" or identity_tags(record.get("home", "")) or identity_tags(record.get("away", "")):
        return {**base, "status": "out_of_scope"}
    try:
        kickoff = iso_time(record["kickoff"])
        day = kickoff.astimezone(LISBON).date().isoformat()
        if record.get("event_date", record.get("date", day)) != day:
            return {**base, "status": "unverified", "reason": "inconsistent_date"}
    except (ValueError, TypeError, KeyError):
        return {**base, "status": "unverified"}
    resource = next((row for row in catalog.get("resources", []) if row.get("league") == league), None)
    if not resource or resource.get("status") not in {"ok", "cached"}:
        return {**base, "status": "unverified", "reason": "calendar_unavailable"}
    if not resource.get("cache_from", "9999") <= day <= resource.get("cache_through", ""):
        return {**base, "status": "unverified", "reason": "outside_calendar_window"}
    same_names = lambda a, b: canonical_team(a) == canonical_team(b) or team_equal(a, b, "football")
    rows = [row for row in resource.get("fixtures", []) if row["date"] == day
            and same_names(record.get("home", ""), row["home"]) and same_names(record.get("away", ""), row["away"])]
    if len(rows) != 1:
        return {**base, "status": "not_found" if not rows else "unverified", "reason": "no_unique_fixture"}
    row = rows[0]
    evidence = {**base, "source_event_id": row["source_event_id"], "source_url": row["source_url"],
                "checked_at": resource["checked_at"], "attribution": ATTRIBUTION, "license": "ODbL-1.0"}
    if abs((iso_time(row["kickoff"]) - kickoff).total_seconds()) > tolerance_minutes * 60:
        return {**evidence, "status": "conflict", "reason": "different_kickoff", "calendar_kickoff": row["kickoff"]}
    return {**evidence, "status": "verified"}
