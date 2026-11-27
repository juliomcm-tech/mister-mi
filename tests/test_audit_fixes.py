import unittest
from datetime import datetime
from consensus.core import UTC, team_equal, name_key
from consensus.espn_results import parse_espn, _result, espn_paths
from consensus.history import record, apply_results, daily_slips

NOW = datetime(2026, 11, 27, 12, tzinfo=UTC)


def comp(state, hs, as_, detail="", lines=None, home="Boston Bruins", away="Toronto Maple Leafs"):
    h = {"homeAway": "home", "score": hs, "team": {"displayName": home}}
    a = {"homeAway": "away", "score": as_, "team": {"displayName": away}}
    if lines:
        h["linescores"] = [{"value": v} for v in lines[0]]
        a["linescores"] = [{"value": v} for v in lines[1]]
    return {"events": [{"competitions": [{"date": "2026-11-21T00:00Z", "status": {"type": {"name": state, "detail": detail}}, "competitors": [h, a]}]}]}


REC = {"id": "x", "sport": "hockey", "home": "Boston Bruins", "away": "Toronto Maple Leafs", "kickoff": "2026-11-21T00:00:00+00:00",
       "market": "FT_1X2", "outcome": "HOME", "competition": "NHL"}


class AuditFixes(unittest.TestCase):
    def test_nhl_final_with_ot_only_in_detail_is_not_settled_without_periods(self):
        g = parse_espn(comp("STATUS_FINAL", "3", "2", "Final/OT"), "hockey")[0]
        self.assertIsNone(_result(REC, g, NOW, "espn", "u"))

    def test_basketball_1x2_needs_regulation_quarters(self):
        r = {**REC, "sport": "basketball", "home": "Boston Celtics", "away": "Denver Nuggets", "competition": "NBA"}
        g = parse_espn(comp("STATUS_FINAL", "110", "108", home="Boston Celtics", away="Denver Nuggets"), "basketball")[0]
        self.assertIsNone(_result(r, g, NOW, "espn", "u"))
        g = parse_espn(comp("STATUS_FINAL", "110", "108", lines=[[25, 25, 25, 25, 10], [25, 25, 25, 25, 8]],
                            home="Boston Celtics", away="Denver Nuggets"), "basketball")[0]
        res = _result(r, g, NOW, "espn", "u")
        self.assertEqual((res["home_score"], res["away_score"]), (100, 100))
        self.assertIsNotNone(_result({**r, "market": "MATCH_WINNER"}, g, NOW, "espn", "u"))

    def test_tennis_retirement_is_void(self):
        r = {**REC, "sport": "tennis", "home": "A Player", "away": "B Player", "market": "MATCH_WINNER", "competition": "ATP"}
        data = {"events": [{"groupings": [{"grouping": {"slug": "mens-singles"}, "competitions": [{"date": "2026-11-21T00:00Z",
                "status": {"type": {"name": "STATUS_FINAL", "detail": "Final - Retired"}}, "competitors": [
                    {"winner": True, "athlete": {"displayName": "A Player"}}, {"winner": False, "athlete": {"displayName": "B Player"}}]}]}]}]}
        self.assertEqual(_result(r, parse_espn(data, "tennis")[0], NOW, "espn", "u")["status"], "void")

    def test_special_letters(self):
        self.assertTrue(team_equal("Wisła Płock", "Wisla Plock", "football"))
        self.assertEqual(name_key("Bodø/Glimt"), "bodo glimt")

    def test_league_paths(self):
        self.assertEqual(espn_paths({"sport": "football", "competition": "England League One", "country": "England"})[0], "soccer/eng.3")
        self.assertEqual(espn_paths({"sport": "football", "competition": "Champions League", "country": "Desconhecido"})[0], "soccer/uefa.champions")

    def test_same_bet_with_new_id_is_not_recorded_twice_and_override_corrects(self):
        pick = {"id": "a", "sport": "football", "home": "Werder Bremen", "away": "Borussia Mgladbach", "kickoff": "2026-11-27T19:30:00+00:00",
                "market": "FT_1X2", "outcome": "HOME", "match": "x", "selection": "y", "odds": 1.7}
        h = record({"records": []}, {"data": [pick], "date": "2026-11-27", "updated_at": "2026-11-27T10:00:00+00:00", "settings": {}})
        h = record(h, {"data": [{**pick, "id": "b", "away": "Borussia Mönchengladbach", "kickoff": "2026-11-27T19:15:00+00:00"}],
                       "date": "2026-11-27", "updated_at": "2026-11-27T11:00:00+00:00", "settings": {}})
        self.assertEqual(len(h["records"]), 1)
        later = datetime(2026, 11, 28, 9, tzinfo=UTC)
        apply_results(h, [{"id": "a", "status": "final", "home_score": 1, "away_score": 1}], later)
        self.assertEqual(h["records"][0]["result"], "loss")
        apply_results(h, [{"id": "a", "status": "final", "home_score": 2, "away_score": 1, "override": True}], later)
        self.assertEqual(h["records"][0]["result"], "win")

    def test_daily_slip_excludes_picks_published_after_first_kickoff(self):
        rows = [{"id": "1", "date": "2026-11-21", "first_seen": "2026-11-21T03:00:00+00:00", "kickoff": "2026-11-21T12:30:00+00:00", "result": "win", "odds": 1.5},
                {"id": "2", "date": "2026-11-21", "first_seen": "2026-11-21T11:00:00+00:00", "kickoff": "2026-11-21T15:00:00+00:00", "result": "win", "odds": 1.6},
                {"id": "3", "date": "2026-11-21", "first_seen": "2026-11-21T19:00:00+00:00", "kickoff": "2026-11-21T20:00:00+00:00", "result": "loss", "odds": 1.4}]
        d = daily_slips(rows)["days"][0]
        self.assertEqual((d["picks"], d["late"], d["status"], d["combined_odds"]), (2, 1, "won", 2.4))


if __name__ == "__main__":
    unittest.main()
