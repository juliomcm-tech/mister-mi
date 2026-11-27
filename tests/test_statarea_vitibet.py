import unittest
from datetime import datetime
from consensus.core import UTC, Tip, analyse
from consensus.sources import parse_statarea, parse_vitibet, FetchError

NOW = datetime(2026, 11, 27, 11, tzinfo=UTC)
URL = "https://www.statarea.com/olddevices/prediction/2026-11-27/"


def statarea(pred="1", pct=(70, 20, 10), goals=(85, 60, 30), bts=(40, 60), s1="-", s2="-"):
    v = list(pct) + [30, 40, 30] + list(goals) + list(bts)
    head = "".join(f"<td>{x}</td>" for x in ["1", "X", "2", "H1", "HX", "H2", "1.5", "2.5", "3.5", "BTS", "OTS"])
    return (f'<table><tr><td><img src="f.png"></td><td colspan="10">Portugal-Liga Portugal</td></tr>'
            f'<tr><td colspan="11">time: 12:00</td></tr><tr><td colspan="10">prediction: <b>{pred}</b></td><td>&nbsp;</td></tr>'
            f'<tr><td colspan="10">Porto</td><td>{s1}</td></tr><tr><td colspan="10">Benfica</td><td>{s2}</td></tr>'
            f'<tr>{head}</tr><tr>{"".join(f"<td><font>{x}%</font></td>" for x in v)}</tr></table>')


class StatareaTests(unittest.TestCase):
    def test_markets_and_no_kickoff(self):
        tips, raw, _ = parse_statarea(statarea(), URL, NOW)
        got = {(t.market, t.outcome): t.metric for t in tips}
        self.assertEqual(raw, 1)
        self.assertEqual(got[("FT_1X2", "HOME")], 70)
        self.assertEqual(got[("FT_TOTAL_1.5", "OVER")], 85)
        self.assertEqual(got[("FT_TOTAL_3.5", "UNDER")], 70)
        self.assertEqual(got[("FT_BTTS", "NO")], 60)
        self.assertTrue(all(t.kickoff is None and t.event_date == "2026-11-27" and t.country == "Portugal" for t in tips))

    def test_finished_and_double_chance(self):
        self.assertEqual(parse_statarea(statarea(s1="2", s2="0"), URL, NOW)[0], [])
        tips = parse_statarea(statarea(pred="1X"), URL, NOW)[0]
        self.assertFalse(any(t.market == "FT_1X2" for t in tips))

    def test_untimed_source_only_confirms(self):
        s = [t for t in parse_statarea(statarea(), URL, NOW)[0] if t.market == "FT_1X2"]
        self.assertEqual(analyse(s, NOW)["total_selected"], 0)
        o = Tip("olbg", "football", "Porto", "Benfica", "2026-11-27", "2026-11-27T20:00:00Z", "FT_1X2", "HOME",
                "https://example.org", NOW.isoformat(), "Portugal Liga Portugal", None, "vote_pct", 18, 22, 1.5, country="Portugal")
        self.assertEqual(analyse(s + [o], NOW)["total_selected"], 1)

    def test_changed_structure(self):
        with self.assertRaises(FetchError):
            parse_statarea("<html></html>", URL, NOW)


class VitibetTests(unittest.TestCase):
    def row(self, tip="1", pct=(68, 20, 12), date="27.11"):
        return (f'<tr><td class="standardbunka">{date}</td><td></td><td class="standardbunka">Porto</td><td class="standardbunka">Benfica</td><td></td>'
                f'<td class="vetsipismo">2</td><td> : </td><td class="vetsipismo">0</td>'
                + "".join(f'<td class="standardbunkaprocenta">{x} %</td>' for x in pct)
                + f'<td class="barvapodtipek1">{tip}</td><td class="standardbunkaprocenta">1.5</td><td></td></tr>')

    def parse(self, *rows):
        html = '<table><tr class="odseknutiligy"><td colspan="14">Portugal Liga Portugal</td></tr>' + "".join(rows) + "</table>"
        return parse_vitibet(html, "https://www.vitibet.com/index.php", NOW)[0]

    def test_single_tip_probability(self):
        t = self.parse(self.row())[0]
        self.assertEqual((t.outcome, t.metric, t.event_date, t.kickoff, t.country), ("HOME", 68, "2026-11-27", None, "Portugal"))

    def test_double_tips_and_draw_code(self):
        self.assertEqual(self.parse(self.row(tip="10")), [])
        self.assertEqual(self.parse(self.row(tip="0", pct=(20, 66, 14)))[0].outcome, "DRAW")


if __name__ == "__main__":
    unittest.main()


class TimingCatalogueTests(unittest.TestCase):
    def test_untimed_models_get_kickoff_from_any_timed_forecast_without_counting_it_as_a_vote(self):
        s = [t for t in parse_statarea(statarea(), URL, NOW)[0] if t.market == "FT_1X2"]
        v = Tip("vitibet", "football", "Porto", "Benfica", "2026-11-27", None, "FT_1X2", "HOME", "https://example.org/v",
                NOW.isoformat(), "Portugal Liga Portugal", 70, "model_pct", country="Portugal")
        # a Zulubet só dá 40% (não passa o limiar) mas tem a hora do jogo
        clock = Tip("zulubet", "football", "Porto", "Benfica", "2026-11-27", "2026-11-27T20:15:00+00:00", "FT_1X2", "DRAW",
                    "https://example.org/z", NOW.isoformat(), "Portugal Liga Portugal", 40, "model_pct", country="Portugal")
        self.assertEqual(analyse(s + [v], NOW)["total_selected"], 0)
        r = analyse(s + [v, clock], NOW)
        self.assertEqual(r["total_selected"], 1)
        self.assertEqual(r["data"][0]["kickoff"], "2026-11-27T20:15:00+00:00")
        self.assertEqual(r["data"][0]["source_count"], 2)

    def test_conflicting_clocks_do_not_anchor(self):
        s = [t for t in parse_statarea(statarea(), URL, NOW)[0] if t.market == "FT_1X2"]
        v = Tip("vitibet", "football", "Porto", "Benfica", "2026-11-27", None, "FT_1X2", "HOME", "https://example.org/v",
                NOW.isoformat(), "Portugal Liga Portugal", 70, "model_pct", country="Portugal")
        c1 = Tip("zulubet", "football", "Porto", "Benfica", "2026-11-27", "2026-11-27T14:00:00+00:00", "FT_1X2", "DRAW",
                 "https://example.org/z", NOW.isoformat(), "x", 40, "model_pct", country="Portugal")
        c2 = Tip("olbg", "football", "Porto", "Benfica", "2026-11-27", "2026-11-27T20:00:00+00:00", "FT_1X2", "AWAY",
                 "https://example.org/o", NOW.isoformat(), "x", None, "vote_pct", 2, 10, country="Portugal")
        self.assertEqual(analyse(s + [v, c1, c2], NOW)["total_selected"], 0)
