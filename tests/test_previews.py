import unittest
from dataclasses import replace
from datetime import datetime, timedelta
from consensus.core import UTC, analyse, upcoming_previews
from consensus.history import record
from test_consensus import NOW, tip


def future_tip(offset, source="olbg", **changes):
    day = (NOW + timedelta(days=offset)).date().isoformat()
    return replace(tip(source), event_date=day, kickoff=day + "T20:00:00Z", **changes)


class PreviewTests(unittest.TestCase):
    def test_same_rules_find_future_consensus_without_creating_recommendations(self):
        records = [future_tip(1), future_tip(1, "forebet"), future_tip(2)]
        self.assertEqual(analyse(records, NOW)["data"], [])
        tomorrow, after = upcoming_previews(records, NOW)
        self.assertEqual([tomorrow["date"], after["date"]], ["2026-11-20", "2026-11-21"])
        self.assertEqual(tomorrow["total_consensus_candidates"], 1)
        self.assertEqual(tomorrow["candidates"][0]["source_count"], 2)
        self.assertFalse(tomorrow["candidates"][0]["is_recommendation"])
        self.assertEqual((tomorrow["total_selected"], tomorrow["data"]), (0, []))
        self.assertEqual(after["total_consensus_candidates"], 0)
        self.assertEqual(len(after["watchlist"]), 1)
        for preview in (tomorrow, after):
            with self.assertRaises(ValueError):
                record({"records": []}, preview)

    def test_preview_uses_real_freshness_clock_and_rejects_old_or_future_fetches(self):
        for fetched in [NOW - timedelta(hours=1), NOW + timedelta(days=1)]:
            with self.subTest(fetched=fetched):
                preview = upcoming_previews([future_tip(1, fetched_at=fetched.isoformat())], NOW)[0]
                self.assertEqual(preview["total_eligible"], 0)
                self.assertEqual(preview["discarded"]["stale"], 1)
        self.assertEqual(upcoming_previews([future_tip(1)], NOW)[0]["total_eligible"], 1)

    def test_future_preview_keeps_thresholds_conflicts_and_exclusions(self):
        cases = [([future_tip(1, votes_total=10, votes_for=9)], {}),
                 ([future_tip(1), future_tip(1, "forebet", outcome="AWAY")], {}),
                 ([future_tip(1)], {"excluded_sports": ["football"]})]
        for records, settings in cases:
            with self.subTest(settings=settings):
                preview = upcoming_previews(records, NOW, settings)[0]
                self.assertEqual((preview["candidates"], preview["watchlist"]), ([], []))

    def test_lisbon_days_cross_year_and_summer_utc_midnight_correctly(self):
        for now, expected in [(datetime(2026, 12, 31, 22, tzinfo=UTC), ["2027-01-01", "2027-01-02"]),
                              (datetime(2026, 7, 1, 23, 5, tzinfo=UTC), ["2026-07-03", "2026-07-04"])]:
            self.assertEqual([p["date"] for p in upcoming_previews([], now)], expected)

    def test_preview_never_relabels_today_or_third_day_forecasts(self):
        snapshots = upcoming_previews([tip(), future_tip(3)], NOW)
        self.assertTrue(all(p["total_eligible"] == 0 for p in snapshots))
        self.assertEqual(record({"records": []}, analyse([tip(), tip("forebet"), future_tip(1)], NOW))["records"][0]["date"], "2026-11-19")


if __name__ == "__main__":
    unittest.main()
