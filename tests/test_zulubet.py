import unittest
from datetime import datetime
from consensus.core import UTC, analyse, Tip
from consensus.sources import parse_zulubet, FetchError

NOW = datetime(2026, 11, 27, 9, 45, tzinfo=UTC)


def row(when, name, probs, tip, extra="", score="", league="Portugal Liga 3"):
    p = "".join(f'<td class="prob prediction_full">{x}%</td>' for x in probs)
    return (f'<tr><td><script>mf_usertime(\'{when}\');</script></td><td><img class="flags" title="{league}"> '
            f'<span class="m2"><a href="https://www.zulubet.com/match-1.html">{name}</a></span></td>'
            f'<td class="prediction_min"><table class="prob_table"><tr><td class="prob">1: {probs[0]}%</td></tr></table></td>{p}'
            f'<td>{extra}<span style="color:green"><b>{tip}</b></span></td><td></td>'
            f'<td class="aver_odds_full">1.40</td><td class="aver_odds_full">4.50</td><td class="aver_odds_full">7.00</td>'
            f'<td>{score}</td><td></td></tr>')


class ZulubetTests(unittest.TestCase):
    def parse(self, *rows):
        return parse_zulubet("<table>" + "".join(rows) + "</table>", "https://www.zulubet.com/", NOW)[0]

    def test_utc_time_selected_probability_and_odds(self):
        t = self.parse(row("11/27/2026, 20:00", "Porto B - Benfica B", [70, 18, 12], "1"))[0]
        self.assertEqual((t.home, t.away, t.outcome, t.metric, t.odds), ("Porto B", "Benfica B", "HOME", 70, 1.40))
        self.assertEqual(t.kickoff, "2026-11-27T20:00:00+00:00")
        self.assertEqual((t.country, t.status, t.market, t.metric_kind), ("Portugal", "scheduled", "FT_1X2", "model_pct"))
        self.assertTrue(t.eligible(analyse([], NOW)["settings"]))

    def test_double_chance_tips_are_ignored(self):
        self.assertEqual(self.parse(row("11/27/2026, 20:00", "A - B", [45, 30, 25], "1X")), [])

    def test_countdown_is_not_live_but_finished_score_is_finished(self):
        a = self.parse(row("11/27/2026, 10:30", "A - B", [20, 15, 65], "2", extra="<span>-45'</span> "))[0]
        self.assertEqual((a.status, a.outcome, a.metric), ("scheduled", "AWAY", 65))
        b = self.parse(row("11/27/2026, 08:00", "C - D", [66, 20, 14], "1", score="2:0"))[0]
        self.assertEqual(b.status, "finished")
        c = self.parse(row("11/27/2026, 09:00", "E - F", [66, 20, 14], "1", extra="<span>52'</span> "))[0]
        self.assertEqual(c.status, "live")

    def test_changed_structure_is_reported(self):
        with self.assertRaises(FetchError):
            parse_zulubet("<html><body>nada</body></html>", "https://www.zulubet.com/", NOW)

    def test_cross_check_with_another_source_produces_a_pick(self):
        z = self.parse(row("11/27/2026, 20:00", "Porto B - Benfica B", [72, 18, 10], "1"))[0]
        o = Tip("olbg", "football", "Porto B", "Benfica B", "2026-11-27", "2026-11-27T20:00:00Z", "FT_1X2", "HOME",
                "https://example.org", NOW.isoformat(), "Portugal Liga 3", None, "vote_pct", 20, 24, 1.5, country="Portugal")
        result = analyse([z, o], NOW)
        self.assertEqual(result["total_selected"], 1)
        self.assertEqual(result["data"][0]["source_count"], 2)


if __name__ == "__main__":
    unittest.main()
