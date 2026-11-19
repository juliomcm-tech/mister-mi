from copy import deepcopy
from datetime import datetime, timezone
import json
import unittest
from unittest.mock import patch

from consensus.free_results import collect_free_results


NOW = datetime(2026, 11, 19, 12, tzinfo=timezone.utc)
RECORD = {"id": "pick-1", "sport": "football", "home": "Bayern Munich", "away": "VfB Stuttgart",
          "date": "2026-11-18", "kickoff": "2026-11-18T19:30:00Z", "country": "Germany",
          "competition": "Germany · Bundesliga", "result": "pending"}
MATCH = {"matchID": 123, "leagueShortcut": "bl1", "leagueSeason": 2026,
         "matchDateTimeUTC": "2026-11-18T19:30:00Z", "matchIsFinished": True,
         "team1": {"teamName": "Bayern Munich"}, "team2": {"teamName": "VfB Stuttgart"},
         "matchResults": [{"resultTypeKind": "HalfTime", "pointsTeam1": 1, "pointsTeam2": 1},
                          {"resultTypeKind": "After90Minutes", "pointsTeam1": 2, "pointsTeam2": 1},
                          {"resultTypeKind": "AfterPenaltyShootout", "pointsTeam1": 5, "pointsTeam2": 4}]}


class FreeResultsTests(unittest.TestCase):
    def run_with(self, matches=None, records=None, history_extra=None):
        history = {"records": [deepcopy(RECORD)] if records is None else records, **(history_extra or {})}
        with patch("consensus.free_results.Client.get", return_value=json.dumps([MATCH] if matches is None else matches)) as get:
            result = collect_free_results(history, NOW)
            return result, get.call_count

    def test_uses_verified_regular_time_not_half_time_or_penalties(self):
        (results, statuses), calls = self.run_with()
        self.assertEqual((results[0]["home_score"], results[0]["away_score"]), (2, 1))
        self.assertEqual(results[0]["source"], "openligadb")
        self.assertEqual(statuses[0]["license"], "ODbL-1.0")
        self.assertEqual(calls, 1)

    def test_rejects_unfinished_missing_or_conflicting_regulation_scores(self):
        for mutate in [lambda x: x.update(matchIsFinished=False),
                       lambda x: x.update(matchResults=x["matchResults"][:1]),
                       lambda x: x["matchResults"].append(deepcopy(x["matchResults"][1])),
                       lambda x: x["matchResults"][1].update(pointsTeam1=True),
                       lambda x: x["matchResults"][1].update(pointsTeam1=-1)]:
            match = deepcopy(MATCH)
            mutate(match)
            (results, _), _ = self.run_with(matches=[match])
            self.assertEqual(results, [])

    def test_requires_country_competition_teams_date_and_time(self):
        for changed in [{"country": "Austria"}, {"competition": "Premier League"},
                        {"sport": "tennis"}, {"date": "2026-11-17"},
                        {"kickoff": "2026-11-18T20:30:00Z"}, {"away": "Stuttgart W"}]:
            (results, _), _ = self.run_with(records=[{**RECORD, **changed}])
            self.assertEqual(results, [])

    def test_ambiguous_duplicate_events_stay_pending(self):
        (results, _), _ = self.run_with(matches=[MATCH, MATCH])
        self.assertEqual(results, [])

    def test_settled_and_future_records_do_not_trigger_calls(self):
        (_, _), calls = self.run_with(records=[{**RECORD, "result": "win"},
                                              {**RECORD, "kickoff": "2026-11-19T20:00:00Z"}])
        self.assertEqual(calls, 0)

    def test_cache_avoids_repeated_network_calls(self):
        (_, statuses), _ = self.run_with()
        (results, cached), calls = self.run_with(history_extra={"result_sources": statuses})
        self.assertEqual(calls, 0)
        self.assertEqual(results, [])
        self.assertEqual(cached[0]["status"], "cached")

    def test_failures_do_not_settle_and_receive_cooldown(self):
        with patch("consensus.free_results.Client.get", side_effect=TimeoutError):
            results, statuses = collect_free_results({"records": [RECORD]}, NOW)
        self.assertEqual(results, [])
        self.assertEqual(statuses[0]["status"], "error")
        self.assertIn("next_check_at", statuses[0])

    def test_one_request_per_league_season_for_multiple_picks(self):
        (results, _), calls = self.run_with(records=[RECORD, {**RECORD, "id": "pick-2"}])
        self.assertEqual(calls, 1)
        self.assertEqual(len(results), 2)


if __name__ == "__main__":
    unittest.main()
