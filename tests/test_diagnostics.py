import unittest
from dataclasses import replace
from datetime import timedelta
from test_consensus import NOW, tip
from consensus.core import analyse
from consensus.history import record


class DiagnosticsTests(unittest.TestCase):
    def test_source_failure_does_not_turn_a_single_provider_into_consensus(self):
        p = analyse([tip(), tip()], NOW)
        self.assertEqual(p['total_selected'], 0)
        self.assertEqual(p['diagnostics']['today_events'], 1)
        self.assertEqual(p['diagnostics']['comparison_rejections']['insufficient_sources'], 1)
        self.assertEqual(len(p['watchlist']), 1)
        self.assertEqual(p['watchlist'][0]['source_count'], 1)
        self.assertFalse(p['watchlist'][0]['is_recommendation'])
        self.assertEqual(record({'records': []}, p)['records'], [])

    def test_forecasts_and_events_are_counted_separately_and_funnel_reconciles(self):
        records = [tip(), tip('forebet'), tip(votes_total=10, votes_for=9),
                   tip(votes_total=20, votes_for=14),
                   tip('protipster', metric=None, metric_kind='missing'), tip(event_date='2026-11-20')]
        p = analyse(records, NOW)
        d = p['diagnostics']
        self.assertEqual((p['total_collected'], d['today_forecasts'], d['today_events']), (6, 5, 1))
        self.assertEqual(d['threshold_reasons'], {'insufficient_votes': 1, 'below_source_threshold': 1, 'missing_metric': 1})
        self.assertEqual(sum(d['threshold_reasons'].values()), p['discarded']['threshold'])
        self.assertEqual(p['total_collected'], p['total_eligible'] + sum(p['discarded'][k] for k in ['other_day', 'started_or_soon', 'stale', 'threshold']))
        self.assertEqual(len(p['watchlist']), 0)

    def test_candidates_remain_subject_to_time_conflict_and_exclusions(self):
        for records, settings in [([tip(kickoff='2026-11-19T11:00:00Z')], {}),
                                  ([tip(fetched_at=(NOW-timedelta(hours=1)).isoformat())], {}),
                                  ([tip(), tip('forebet', outcome='AWAY')], {}),
                                  ([tip()], {'excluded_countries': ['Portugal']}),
                                  ([tip('predictz')], {})]:
            with self.subTest(records=records, settings=settings):
                p = analyse(records, NOW, settings)
                self.assertEqual(p['watchlist'], [])
                self.assertEqual(p['data'], [])

    def test_diagnostics_and_candidates_are_stable_across_input_order(self):
        records = [tip(), replace(tip(), home='Sporting', away='Braga')]
        a, b = analyse(records, NOW), analyse(list(reversed(records)), NOW)
        self.assertEqual(a['watchlist'], b['watchlist'])
        self.assertEqual(a['diagnostics'], b['diagnostics'])


if __name__ == '__main__':
    unittest.main()
