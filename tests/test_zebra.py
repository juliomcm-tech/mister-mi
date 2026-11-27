import unittest
from datetime import datetime
from consensus.core import Tip, UTC, analyse
from consensus.history import record, summary, apply_results

NOW = datetime(2026, 11, 27, 9, 45, tzinfo=UTC)


def pair(odds_olbg, odds_zulu, home="Porto B", away="Benfica B", kickoff="2026-11-27T20:00:00Z"):
    o = Tip("olbg", "football", home, away, "2026-11-27", kickoff, "FT_1X2", "AWAY", "https://example.org/o",
            NOW.isoformat(), "Portugal Liga 3", 85.0, "vote_pct", 17, 20, odds_olbg, country="Portugal")
    z = Tip("zulubet", "football", home, away, "2026-11-27", kickoff, "FT_1X2", "AWAY", "https://example.org/z",
            NOW.isoformat(), "Portugal Liga 3", 68.0, "model_pct", odds=odds_zulu, country="Portugal")
    return [o, z]


class ZebraTests(unittest.TestCase):
    def test_high_odds_consensus_goes_to_zebras_not_to_selection(self):
        r = analyse(pair(2.6, 2.45), NOW)
        self.assertEqual(r["total_selected"], 0)
        self.assertEqual(r["total_zebras"], 1)
        z = r["zebras"][0]
        self.assertTrue(z["zebra"])
        self.assertEqual(z["odds"], 2.45)  # o preço mais baixo observado, por prudência
        self.assertEqual(z["implied_pct"], round(100 / 2.45, 1))
        self.assertEqual({s["source"] for s in z["source_says"]}, {"olbg", "zulubet"})

    def test_normal_odds_stay_in_selection(self):
        r = analyse(pair(1.8, 1.75), NOW)
        self.assertEqual((r["total_selected"], r["total_zebras"]), (1, 0))

    def test_odds_spread_warning(self):
        z = analyse(pair(3.4, 2.3), NOW)["zebras"][0]
        self.assertTrue(any("diferem" in w for w in z["zebra_warnings"]))

    def test_zebras_have_separate_stats(self):
        payload = analyse(pair(2.6, 2.45) + pair(1.8, 1.75, home="Sporting B", away="Braga B"), NOW)
        h = record({"records": []}, payload)
        ids = {p["id"]: p for p in h["records"]}
        zid = payload["zebras"][0]["id"]
        nid = payload["data"][0]["id"]
        later = datetime(2026, 11, 28, 9, tzinfo=UTC)
        apply_results(h, [{"id": zid, "status": "final", "home_score": 0, "away_score": 2},
                          {"id": nid, "status": "final", "home_score": 1, "away_score": 0}], later)
        s = summary(h, {})
        self.assertEqual(s["overall"]["settled"], 1)            # só a normal
        self.assertEqual(s["overall"]["losses"], 1)
        self.assertEqual((s["zebra"]["settled"], s["zebra"]["wins"]), (1, 1))
        self.assertEqual(s["daily"]["days"][0]["picks"], 1)    # a zebra não entra no boletim do dia
        self.assertEqual(ids[zid]["kind"], "zebra")


if __name__ == "__main__":
    unittest.main()
