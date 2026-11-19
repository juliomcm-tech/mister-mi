import importlib.util
from pathlib import Path
import unittest

MODULE = Path(__file__).resolve().parents[1] / "scripts" / "audit_coverage.py"
spec = importlib.util.spec_from_file_location("audit_coverage", MODULE)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class CoverageAuditTests(unittest.TestCase):
    def test_missing_or_duplicated_provider_never_becomes_independent_confirmation(self):
        checks = audit.synthetic_rule_checks()
        self.assertTrue(checks["not_live_forecasts"])
        cases = checks["scenarios"]
        self.assertEqual(cases["two_agreeing_independent_providers"]["consensus_candidates"], 1)
        for name in ["second_provider_unavailable", "five_duplicate_pages_of_one_provider",
                     "independent_provider_disagrees", "wrong_lisbon_day", "old_collection"]:
            self.assertEqual(cases[name]["consensus_candidates"], 0)

    def test_screenshot_claims_cannot_be_outputs_of_the_deployed_formula(self):
        report = audit.screenshot_score_audit()
        self.assertEqual([row["score_using_repository_formula"] for row in report["claims"]], [89.1, 89.4, 77.2, 79.0])
        self.assertTrue(all(row["claimed_score"] != row["score_using_repository_formula"] for row in report["claims"]))
        self.assertEqual(report["maximum_two_source_score"], 82)
        self.assertEqual(report["maximum_three_source_score"], 94)

    def test_audit_reports_only_configured_sports_and_never_updates_live_settings(self):
        from consensus.core import DEFAULTS, UTC
        from datetime import datetime
        before = dict(DEFAULTS)
        report = audit.build_report([], datetime(2026, 11, 19, 12, tzinfo=UTC), [])
        self.assertEqual(len(report["configured_sports"]), 5)
        self.assertFalse(report["covers_all_sports_or_daily_fixtures"])
        self.assertFalse(report["threshold_sensitivity"]["live_settings_updated"])
        self.assertEqual(len(report["threshold_sensitivity"]["scenarios"]), 12)
        self.assertEqual(DEFAULTS, before)


if __name__ == "__main__":
    unittest.main()
