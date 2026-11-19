"""Bounded result verification through the official OpenLigaDB API.

This is result evidence, never an additional prediction vote. Openfootball is
deliberately not an automatic settlement source: its records may omit time zones
and its upstream updates do not guarantee current results.
"""
from __future__ import annotations

from datetime import datetime, timedelta
import json
import re

from .core import LISBON, UTC, iso_time, name_key, team_equal
from .sources import Client, FetchError

ATTRIBUTION = "Data from OpenLigaDB (www.openligadb.de), licensed under ODbL 1.0"
LICENSE_URL = "https://www.openligadb.de/en/license"
BASE_URL = "https://api.openligadb.de/getmatchdata/"
MAX_RESOURCES = 4


def _league(record: dict) -> str | None:
    if record.get("sport") != "football" or record.get("country") != "Germany":
        return None
    raw = record.get("competition", "")
    if not isinstance(raw, str):
        return None
    competition = name_key(raw)
    competition = re.sub(r"^(?:germany|german)\s+", "", competition)
    competition = re.sub(r"\s+20\d{2}(?:\s+20\d{2})?$", "", competition).strip()
    if competition in {"bundesliga", "1 bundesliga", "bundesliga 1", "bundesliga i"}:
        return "bl1"
    if competition in {"2 bundesliga", "bundesliga 2", "bundesliga ii"}:
        return "bl2"
    return None


def _scores(match: dict) -> tuple[int, int] | None:
    if match.get("matchIsFinished") is not True:
        return None
    candidates = []
    for result in match.get("matchResults", []):
        if not isinstance(result, dict) or result.get("resultTypeKind") != "After90Minutes":
            continue
        scores = result.get("pointsTeam1"), result.get("pointsTeam2")
        if all(type(value) is int and 0 <= value <= 50 for value in scores):
            candidates.append(scores)
    # Duplicate/conflicting official-time entries are not silently resolved.
    return candidates[0] if len(candidates) == 1 else None


def _matches(record: dict, match: dict, league: str, season: int) -> bool:
    try:
        if match.get("leagueShortcut") != league or match.get("leagueSeason") != season:
            return False
        kickoff = iso_time(record["kickoff"])
        actual = iso_time(match["matchDateTimeUTC"])
        if abs((kickoff - actual).total_seconds()) > 20 * 60:
            return False
        if kickoff.astimezone(LISBON).date() != actual.astimezone(LISBON).date():
            return False
        if record.get("date") and record["date"] != kickoff.astimezone(LISBON).date().isoformat():
            return False
        return (team_equal(record["home"], match["team1"]["teamName"], "football")
                and team_equal(record["away"], match["team2"]["teamName"], "football"))
    except (KeyError, TypeError, ValueError, AttributeError):
        return False


def collect_free_results(history: dict, now: datetime) -> tuple[list[dict], list[dict]]:
    """Return confirmed regulation scores and per-resource collection statuses.

    Persist the returned statuses in ``history['result_sources']`` to respect
    each ``next_check_at`` across refreshes. Successful resources are checked at
    most every six hours; failures get a thirty-minute cooldown. No final score
    is inferred from a prediction, an in-progress score, or a half-time score.
    """
    if now.tzinfo is None:
        raise ValueError("now must contain a time zone")
    now = now.astimezone(UTC)
    grouped: dict[tuple[str, int], list[dict]] = {}
    records = history.get("records", [])
    for record in records if isinstance(records, list) else []:
        if not isinstance(record, dict) or record.get("result") != "pending" or not record.get("id"):
            continue
        league = _league(record)
        if league is None:
            continue
        try:
            kickoff = iso_time(record["kickoff"])
            if now < kickoff + timedelta(minutes=90):
                continue
            local = kickoff.astimezone(LISBON)
            season = local.year if local.month >= 7 else local.year - 1
            grouped.setdefault((league, season), []).append(record)
        except (KeyError, ValueError, TypeError):
            continue
    previous = {}
    prior_statuses = history.get("result_sources", [])
    for status in prior_statuses if isinstance(prior_statuses, list) else []:
        if isinstance(status, dict) and status.get("id") == "openligadb":
            previous[status.get("resource")] = status
    client = Client()
    results, statuses = [], []
    resources = sorted(grouped.items(), key=lambda item: item[0][1], reverse=True)[:MAX_RESOURCES]
    for (league, season), pending in resources:
        resource = f"{league}/{season}"
        url = BASE_URL + resource
        old = previous.get(resource, {})
        try:
            if old.get("next_check_at") and iso_time(old["next_check_at"]) > now:
                statuses.append({**old, "status": "cached", "message": "Intervalo de atualização respeitado"})
                continue
        except (ValueError, TypeError):
            pass
        status = {"id": "openligadb", "name": "OpenLigaDB", "resource": resource,
                  "url": url, "checked_at": now.isoformat(), "attribution": ATTRIBUTION,
                  "license": "ODbL-1.0", "license_url": LICENSE_URL, "collected": 0}
        try:
            data = json.loads(client.get(url, check_robots=False))
            if not isinstance(data, list) or len(data) > 1000:
                raise FetchError("Formato de resultados OpenLigaDB inesperado")
            valid = [item for item in data if isinstance(item, dict) and _scores(item) is not None]
            for record in pending:
                matching = [match for match in valid if _matches(record, match, league, season)]
                if len(matching) != 1:
                    continue
                match = matching[0]
                home, away = _scores(match)
                results.append({"id": record["id"], "status": "final", "home_score": home,
                                "away_score": away, "source": "openligadb",
                                "source_url": url, "source_event_id": str(match.get("matchID", "")),
                                "verified_at": now.isoformat(), "attribution": ATTRIBUTION,
                                "license": "ODbL-1.0"})
                status["collected"] += 1
            status.update(status="ok", message="Resultados regulamentares verificados",
                          next_check_at=(now + timedelta(hours=6)).isoformat())
        except Exception as exc:
            message = str(exc) if isinstance(exc, FetchError) else "Dados OpenLigaDB indisponíveis ou inválidos"
            status.update(status="error", message=message,
                          next_check_at=(now + timedelta(minutes=30)).isoformat())
        statuses.append(status)
    return results, statuses
