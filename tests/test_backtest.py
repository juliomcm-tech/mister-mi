from copy import deepcopy
import importlib.util
from math import log
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location("mister_mi_backtest", Path(__file__).parents[1] / "scripts/backtest.py")
bt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bt)


def game(day, home="A", away="B", hg=2, ag=1):
    return {"league": "test", "date": day, "home": home, "away": away, "home_goals": hg, "away_goals": ag}


TEST_CONFIG = {**bt.CONFIG, "test_start": "2024-01-10", "test_end": "2024-01-31",
               "min_league_games": 1, "min_team_games": 1}


class BacktestTests(unittest.TestCase):
    def test_future_outcome_cannot_change_earlier_prediction(self):
        data = [game("2024-01-01"), game("2024-01-10"), game("2024-01-11")]
        changed = deepcopy(data)
        changed[-1].update(home_goals=0, away_goals=10)
        original = bt.walk_forward(data, TEST_CONFIG)["sample_predictions"][0]
        altered = bt.walk_forward(changed, TEST_CONFIG)["sample_predictions"][0]
        self.assertEqual(original["probabilities"], altered["probabilities"])
        self.assertEqual(original["trained_through"], "2024-01-01")

    def test_same_day_outcome_and_input_order_do_not_leak(self):
        data = [game("2024-01-01"), game("2024-01-10"), game("2024-01-10", "B", "A")]
        original = bt.walk_forward(data, TEST_CONFIG)
        changed = deepcopy(data)
        changed[1].update(home_goals=9, away_goals=0)
        altered = bt.walk_forward(list(reversed(changed)), TEST_CONFIG)
        op = [r["probabilities"] for r in original["sample_predictions"]]
        ap = [r["probabilities"] for r in altered["sample_predictions"]]
        self.assertEqual(op, ap)
        self.assertEqual([r["training_games"] for r in altered["sample_predictions"]], [1, 1])

    def test_previous_day_can_update_next_prediction(self):
        data = [game("2024-01-01"), game("2024-01-10"), game("2024-01-11")]
        changed = deepcopy(data)
        changed[1].update(home_goals=9, away_goals=0)
        a = bt.walk_forward(data, TEST_CONFIG)["sample_predictions"][-1]
        b = bt.walk_forward(changed, TEST_CONFIG)["sample_predictions"][-1]
        self.assertNotEqual(a["probabilities"], b["probabilities"])
        self.assertEqual(a["trained_through"], "2024-01-10")

    def test_cold_start_uses_both_team_and_league_minimums(self):
        state = bt.empty_state()
        self.assertIsNone(bt.predict(state, game("2024-01-10")))
        for _ in range(60):
            bt.learn(state, game("2024-01-01"))
        self.assertIsNotNone(bt.predict(state, game("2024-01-10")))
        self.assertIsNone(bt.predict(state, game("2024-01-10", "C", "A")))

    def test_probability_and_scoring_conventions(self):
        probs = bt.poisson_probs(1.5, 1.5)
        self.assertAlmostEqual(sum(probs), 1)
        self.assertAlmostEqual(probs[0], probs[2])
        self.assertAlmostEqual(bt.brier([.7, .2, .1], 0), .14)
        self.assertAlmostEqual(bt.logloss([.7, .2, .1], 0), -log(.7))
        self.assertEqual(bt.wilson(0, 0), None)
        lo, hi = bt.wilson(5, 10)
        self.assertLess(lo, 50)
        self.assertGreater(hi, 50)

    def test_explicit_fulltime_only(self):
        import json
        raw = json.dumps({"matches": [
            {"date": "2024-08-01", "team1": "A", "team2": "B", "score": {"ft": [2, 1]}},
            {"date": "2024-08-02", "team1": "A", "team2": "B", "score": [2, 1]},
            {"date": "2024-08-03", "team1": "A", "team2": "B", "score": {"ht": [2, 1]}},
            {"date": "2026-08-01", "team1": "A", "team2": "B", "score": {"ft": [2, 1]}},
        ]})
        games, excluded = bt.parse_source(raw, "en.1", "2024-25")
        self.assertEqual(len(games), 1)
        self.assertEqual(excluded, 3)

    def test_current_fixture_result_is_not_model_input(self):
        state = bt.empty_state()
        for _ in range(60):
            bt.learn(state, game("2024-01-01"))
        a = bt.predict(state, game("2024-01-10", hg=0, ag=20))
        b = bt.predict(state, game("2024-01-10", hg=20, ag=0))
        self.assertEqual(a, b)

    def test_baselines_and_model_have_identical_evaluation_cohort(self):
        data = [game("2024-01-01"), game("2024-01-10"),
                game("2024-01-11", "A", "C"), game("2024-01-12", hg=0, ag=2)]
        report = bt.walk_forward(data, TEST_CONFIG)
        rows = report["_evaluation_ledger"]
        self.assertEqual(report["overall"]["evaluated"], len(rows))
        self.assertEqual(report["warmup_excluded"], 1)
        self.assertEqual(len(report["_prediction_ledger"]), len(rows))
        self.assertAlmostEqual(report["overall"]["always_home_accuracy_pct"],
                               100 * sum(r["actual"] == "HOME" for r in rows) / len(rows))
        self.assertTrue(all(r["trained_through"] < r["date"] for r in rows))
        self.assertEqual(bt.digest(report["_prediction_ledger"]), report["prediction_ledger_sha256"])


if __name__ == "__main__":
    unittest.main()
