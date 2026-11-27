import unittest
from datetime import datetime
from consensus.core import UTC
from consensus.espn_results import parse_espn, parse_zulubet_scores, _orient, _result, espn_paths
from consensus.history import settlement, daily_slips

NOW = datetime(2026, 11, 27, 12, tzinfo=UTC)


def rec(**k):
    base = {"id": "a1", "sport": "football", "home": "Man City", "away": "Fulham", "kickoff": "2026-11-21T12:30:00+00:00",
            "market": "FT_1X2", "outcome": "HOME", "competition": "England Premier League", "result": "pending", "date": "2026-11-21"}
    base.update(k)
    return base


def soccer(state="STATUS_FULL_TIME", hs="1", as_="1"):
    return {"events": [{"id": "9", "date": "2026-11-21T12:30Z", "competitions": [{"id": "9", "date": "2026-11-21T12:30Z",
            "status": {"type": {"name": state}}, "competitors": [
                {"homeAway": "home", "score": hs, "team": {"displayName": "Manchester City"}},
                {"homeAway": "away", "score": as_, "team": {"displayName": "Fulham"}}]}]}]}


class PublicResults(unittest.TestCase):
    def test_soccer_full_time_settles_with_aliases(self):
        g = parse_espn(soccer(), "football")[0]
        r = rec()
        res = _result(r, _orient(r, g, "football"), NOW, "espn", "u")
        self.assertEqual((res["status"], res["home_score"], res["away_score"]), ("final", 1, 1))
        self.assertEqual(settlement(r, res), "loss")

    def test_extra_time_does_not_settle_ninety_minutes(self):
        g = parse_espn(soccer("STATUS_FINAL_AET", "2", "1"), "football")[0]
        self.assertIsNone(_result(rec(), g, NOW, "espn", "u"))

    def test_postponed_is_void_only_after_48h(self):
        g = parse_espn(soccer("STATUS_POSTPONED", "0", "0"), "football")[0]
        self.assertIsNone(_result(rec(kickoff="2026-11-26T20:00:00+00:00"), g, NOW, "espn", "u"))
        self.assertEqual(_result(rec(), g, NOW, "espn", "u")["status"], "void")

    def test_tennis_order_can_be_swapped(self):
        data = {"events": [{"groupings": [{"grouping": {"slug": "mens-singles"}, "competitions": [{"id": "3", "date": "2026-11-19T19:40Z",
                "status": {"type": {"name": "STATUS_FINAL"}}, "competitors": [
                    {"winner": False, "athlete": {"displayName": "Arthur Fils"}},
                    {"winner": True, "athlete": {"displayName": "Alexander Zverev"}}]}]},
                {"grouping": {"slug": "mens-doubles"}, "competitions": []}]}]}
        r = rec(sport="tennis", home="Alexander Zverev", away="Arthur Fils", kickoff="2026-11-19T19:30:00+00:00",
                market="MATCH_WINNER", competition="ATP Finals")
        g = _orient(r, parse_espn(data, "tennis")[0], "tennis")
        res = _result(r, g, NOW, "espn", "u")
        self.assertEqual(settlement(r, res), "win")

    def test_hockey_regulation_uses_three_periods(self):
        data = {"events": [{"competitions": [{"date": "2026-11-21T00:00Z", "status": {"type": {"name": "STATUS_FINAL_OT"}}, "competitors": [
            {"homeAway": "home", "score": "3", "team": {"displayName": "Boston Bruins"}, "linescores": [{"value": 1}, {"value": 1}, {"value": 0}, {"value": 1}]},
            {"homeAway": "away", "score": "2", "team": {"displayName": "Toronto Maple Leafs"}, "linescores": [{"value": 0}, {"value": 1}, {"value": 1}, {"value": 0}]}]}]}]}
        r = rec(sport="hockey", home="Boston Bruins", away="Toronto Maple Leafs", kickoff="2026-11-21T00:00:00+00:00", competition="NHL")
        res = _result(r, parse_espn(data, "hockey")[0], NOW, "espn", "u")
        self.assertEqual((res["home_score"], res["away_score"]), (2, 2))
        self.assertEqual(settlement(r, res), "loss")

    def test_zulubet_past_rows_without_links(self):
        html = ('<table><tr><td><script>mf_usertime(\'11/25/2026, 23:00\');</script></td><td><img class="flags" title="Brazil Serie A"> Atletico-MG - Corinthians</td>'
                '<td class="prob prediction_full">26%</td><td class="prob prediction_full">41%</td><td class="prob prediction_full">32%</td>'
                '<td><b>X2</b></td><td></td><td class="aver_odds_full">2.38</td><td class="aver_odds_full">3.32</td><td class="aver_odds_full">2.92</td>'
                '<td style="text-align: center;">1:1</td><td></td></tr></table>')
        g = parse_zulubet_scores(html)[0]
        self.assertEqual((g["home"][0], g["away"][0], g["hs"], g["as_"]), ("Atletico-MG", "Corinthians", 1, 1))

    def test_paths(self):
        self.assertEqual(espn_paths(rec()), ["soccer/all"])
        self.assertEqual(espn_paths(rec(sport="basketball", competition="Euroleague")), ["basketball/euroleague"])

    def test_daily_slip(self):
        rows = [rec(id="1", result="win", odds=1.5), rec(id="2", result="win", odds=2.0),
                rec(id="3", result="loss", odds=1.8, date="2026-11-22"), rec(id="4", result="pending", odds=1.4, date="2026-11-23")]
        d = daily_slips(rows)
        by = {x["date"]: x for x in d["days"]}
        self.assertEqual((by["2026-11-21"]["status"], by["2026-11-21"]["combined_odds"]), ("won", 3.0))
        self.assertEqual(by["2026-11-22"]["status"], "lost")
        self.assertEqual(by["2026-11-23"]["status"], "pending")
        self.assertEqual((d["settled"], d["won"]), (2, 1))


if __name__ == "__main__":
    unittest.main()
