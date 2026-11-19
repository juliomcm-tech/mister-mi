import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from scripts.pipeline_health import build_pipeline_health, collect_pipeline_health

NOW = datetime(2026, 11, 19, 17, tzinfo=timezone.utc)
WORKFLOW = {"id": 123, "state": "active"}


def run(event="push", created="2026-11-19T16:55:00Z", **changes):
    return {"path": ".github/workflows/collect.yml", "workflow_id": 123, "created_at": created,
            "event": event, "status": "completed", "conclusion": "success", **changes}


class PipelineHealthTests(unittest.TestCase):
    def test_active_workflow_and_successful_pushes_do_not_prove_a_schedule(self):
        result = build_pipeline_health([run(), run("dynamic", path="dynamic/pages")], NOW, WORKFLOW)
        self.assertEqual(result["scheduler_status"], "not_observed")
        self.assertIsNone(result["last_scheduled_at"])
        self.assertEqual(result["schedule_runs_observed"], 0)

    def test_recent_successful_schedule_is_observed_but_an_old_one_is_overdue(self):
        recent = build_pipeline_health([run("schedule")], NOW, WORKFLOW)
        self.assertEqual((recent["scheduler_status"], recent["scheduled_age_minutes"]), ("observed", 5.0))
        old = build_pipeline_health([run("schedule", "2026-11-19T15:55:00Z")], NOW, WORKFLOW)
        self.assertEqual(old["scheduler_status"], "overdue")

    def test_other_workflows_and_future_or_unzoned_timestamps_cannot_prove_a_schedule(self):
        records = [run("schedule", path="other.yml", workflow_id=456),
                   run("schedule", "2026-11-20T16:55:00Z"), run("schedule", "2026-11-19T16:55:00")]
        self.assertEqual(build_pipeline_health(records, NOW, WORKFLOW)["schedule_runs_observed"], 0)

    def test_failed_running_and_disabled_states_remain_distinct(self):
        self.assertEqual(build_pipeline_health([run("schedule", conclusion="failure")], NOW, WORKFLOW)["scheduler_status"], "failed")
        self.assertEqual(build_pipeline_health([run("schedule", status="in_progress", conclusion=None)], NOW, WORKFLOW)["scheduler_status"], "running")
        self.assertEqual(build_pipeline_health([run("schedule")], NOW, {**WORKFLOW, "state": "disabled_manually"})["scheduler_status"], "disabled")

    def test_last_success_and_actual_last_event_are_sorted_independently(self):
        result = build_pipeline_health([run("schedule", "2026-11-19T16:40:00Z"), run(),
                                        run("schedule", "2026-11-19T16:50:00Z", conclusion="failure")], NOW, WORKFLOW)
        self.assertEqual(result["last_event"], "push")
        self.assertEqual(result["last_scheduled_at"], "2026-11-19T16:50:00+00:00")
        self.assertEqual(result["last_successful_scheduled_at"], "2026-11-19T16:40:00+00:00")

    def test_network_failure_is_unavailable_not_a_successful_empty_history(self):
        with patch("scripts.pipeline_health._public_json", side_effect=TimeoutError):
            result = collect_pipeline_health(now=NOW)
        self.assertEqual(result["scheduler_status"], "unavailable")
        self.assertIsNone(result["run_window"])
        self.assertEqual(set(result["errors"]), {"runs", "workflow"})

    def test_invalid_repository_is_rejected_before_any_request(self):
        with patch("scripts.pipeline_health._public_json") as fetch:
            with self.assertRaises(ValueError):
                collect_pipeline_health("https://attacker.example/private", NOW)
            fetch.assert_not_called()

    def test_read_only_collection_accepts_a_genuine_zero_schedule_window(self):
        def response(url):
            return WORKFLOW if "/workflows/" in url else {"workflow_runs": [run()]}
        with patch("scripts.pipeline_health._public_json", side_effect=response) as fetch:
            result = collect_pipeline_health(now=NOW)
        self.assertEqual(fetch.call_count, 2)
        self.assertEqual(result["scheduler_status"], "not_observed")
        self.assertEqual(result["errors"], {})


if __name__ == "__main__":
    unittest.main()
