import json
import unittest
from datetime import datetime, timedelta

from consensus.core import UTC
from consensus.fixture_catalog import collect_fixture_catalog, verify_fixture, _normalise

NOW = datetime(2026, 11, 19, 16, tzinfo=UTC)


def fixture(league="bl1", **changes):
    return {"matchID": 83237 if league == "bl1" else 83697, "leagueShortcut": league, "leagueSeason": 2026,
            "matchDateTimeUTC": "2026-11-20T19:30:00Z", "matchIsFinished": False,
            "team1": {"teamName": "FC Bayern München" if league == "bl1" else "SV Darmstadt 98"},
            "team2": {"teamName": "1. FC Köln" if league == "bl1" else "1. FC Heidenheim 1846"}, **changes}


class FakeClient:
    def __init__(self, data=None, fail=False):
        self.calls = []
        self.data = data
        self.fail = fail

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if self.fail:
            raise RuntimeError("Unavailable")
        league = "bl2" if "/bl2/" in url else "bl1"
        return json.dumps(self.data if self.data is not None else [fixture(league)])


class FixtureCatalogTests(unittest.TestCase):
    def test_two_bounded_requests_and_calendar_is_never_prediction_evidence(self):
        client = FakeClient()
        catalog = collect_fixture_catalog(None, NOW, client=client)
        self.assertEqual(len(client.calls), 2)
        self.assertTrue(all(kwargs == {"check_robots": False} for _, kwargs in client.calls))
        self.assertEqual(catalog["counts_by_date"][1]["scheduled"], 2)
        self.assertFalse(catalog["counts_as_prediction"])
        self.assertFalse(catalog["complete_global_coverage"])
        self.assertTrue(all(row["license"] == "ODbL-1.0" for row in catalog["fixtures"]))

    def test_six_hour_cache_persists_verification_time_and_survives_midnight(self):
        first_client = FakeClient()
        start = datetime(2026, 11, 19, 23, tzinfo=UTC)
        first = collect_fixture_catalog({}, start, client=first_client)
        next_client = FakeClient(fail=True)
        next_result = collect_fixture_catalog(first, start + timedelta(hours=2), client=next_client)
        self.assertEqual(next_client.calls, [])
        self.assertEqual(next_result["status"], "cached")
        self.assertEqual(next_result["counts_by_date"][0]["date"], "2026-11-20")
        self.assertEqual(next_result["resources"][0]["checked_at"], start.isoformat())

    def test_errors_have_persistent_exponential_backoff_and_unknown_counts(self):
        first = collect_fixture_catalog({}, NOW, client=FakeClient(fail=True))
        self.assertEqual(first["status"], "error")
        self.assertTrue(all(row["scheduled"] is None for row in first["counts_by_date"]))
        client = FakeClient()
        second = collect_fixture_catalog(first, NOW + timedelta(minutes=5), client=client)
        self.assertEqual(client.calls, [])
        self.assertEqual(second["status"], "error")
        third = collect_fixture_catalog(second, NOW + timedelta(minutes=31), client=FakeClient(fail=True))
        self.assertEqual(third["resources"][0]["failures"], 2)
        self.assertEqual(third["resources"][0]["next_check_at"], (NOW + timedelta(minutes=91)).isoformat())

    def test_empty_season_does_not_mean_zero_real_world_matches(self):
        catalog = collect_fixture_catalog({}, NOW, client=FakeClient(data=[]))
        self.assertEqual(catalog["status"], "error")
        self.assertFalse(catalog["complete_within_configured_resources"])

    def test_cancelled_wrong_scope_naive_dates_and_conflicting_ids_are_excluded(self):
        valid = fixture()
        wrong = [fixture(matchDateTimeUTC="2026-11-20T19:30:00"), fixture(cancelled=True),
                 fixture(leagueSeason=2025), fixture(matchIsFinished=None), fixture(matchID=True),
                 fixture(team1={"teamName": "Bayern Women"})]
        self.assertEqual(_normalise(wrong, "bl1", 2026), [])
        self.assertEqual(_normalise([valid, fixture(matchDateTimeUTC="2026-11-20T20:30:00Z")], "bl1", 2026), [])

    def test_known_aliases_match_both_teams_date_country_league_and_time(self):
        catalog = collect_fixture_catalog({}, NOW, client=FakeClient())
        record = {"sport": "football", "country": "Germany", "competition": "Germany Bundesliga I",
                  "home": "Bayern Munich", "away": "Cologne", "event_date": "2026-11-20", "kickoff": "2026-11-20T19:30:00Z"}
        verified = verify_fixture(record, catalog)
        self.assertEqual(verified["status"], "verified")
        self.assertEqual(verified["source_event_id"], "83237")
        self.assertFalse(verified["counts_as_prediction"])
        for change in [{"country": "Desconhecido"}, {"sport": "basketball"}, {"segment": "w"},
                       {"home": "Bayern Munich II"}, {"competition": "Germany Bundesliga II"},
                       {"away": "Other club"}, {"event_date": "2026-11-21"}, {"home": None}]:
            self.assertNotEqual(verify_fixture({**record, **change}, catalog)["status"], "verified")
        self.assertEqual(verify_fixture({**record, "kickoff": "2026-11-20T20:30:00Z"}, catalog)["status"], "conflict")

    def test_started_cached_matches_are_not_counted_as_still_upcoming(self):
        catalog = collect_fixture_catalog({}, NOW, client=FakeClient())
        next_day = datetime(2026, 11, 20, 20, tzinfo=UTC)
        # Force a valid fresh cache describing a fixture whose kickoff has passed.
        for resource in catalog["resources"]:
            resource["checked_at"] = next_day.isoformat()
            resource["next_check_at"] = (next_day + timedelta(hours=6)).isoformat()
        result = collect_fixture_catalog(catalog, next_day, client=FakeClient(fail=True))
        self.assertEqual(result["counts_by_date"][0]["scheduled"], 0)
        self.assertTrue(all(row["status"] == "started_unconfirmed" for row in result["fixtures"]))


if __name__ == "__main__":
    unittest.main()
