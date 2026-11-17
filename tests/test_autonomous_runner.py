"""Unit tests for the autonomous benchmark runner, matrix completion, and fail-closed integrity."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from benchmarks.v18.autonomous_runner import (
    check_benchmark_matrix,
    get_completed_tasks_count,
    is_benchmark_complete,
    is_valid_evaluation_row,
    run_post_benchmark_pipeline,
)


class TestAutonomousRunner(unittest.TestCase):

    def test_task_counting(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            self.assertEqual(get_completed_tasks_count(p, 22), 0)
            self.assertFalse(is_benchmark_complete(p, 22))

            # create 1 completed file with valid terminal evaluation evidence
            t1 = p / "task1-live.json"
            t1.write_text(json.dumps({
                "rows": [
                    {"key": "1:resample", "condition": "resample", "repetition": 1, "success": True, "heldout": {"passed": True}, "history": []},
                    {"key": "1:feedback", "condition": "feedback", "repetition": 1, "success": True, "heldout": {"passed": True}, "history": []},
                    {"key": "1:counterfactual", "condition": "counterfactual", "repetition": 1, "success": True, "heldout": {"passed": True}, "history": []},
                ],
                "pending": {}
            }), encoding="utf-8")
            self.assertEqual(get_completed_tasks_count(p, 22), 1)

            # create incomplete file (with pending)
            t2 = p / "task2-live.json"
            t2.write_text(json.dumps({
                "rows": [
                    {"key": "1:resample", "condition": "resample", "repetition": 1, "success": True, "heldout": {"passed": True}, "history": []}
                ],
                "pending": {"1:feedback": []}
            }), encoding="utf-8")
            self.assertEqual(get_completed_tasks_count(p, 22), 1)

    def test_repetition_aware_matrix_checking(self):
        """Verify that multiple repetitions must all be completed to satisfy matrix."""
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            target = [{"id": "t1"}]

            # Repetition 1 only
            t1 = p / "t1-live.json"
            t1.write_text(json.dumps({
                "rows": [
                    {"condition": "resample", "repetition": 1, "success": True, "heldout": {"passed": True}, "history": []},
                    {"condition": "feedback", "repetition": 1, "success": True, "heldout": {"passed": True}, "history": []},
                    {"condition": "counterfactual", "repetition": 1, "success": True, "heldout": {"passed": True}, "history": []},
                ],
                "pending": {}
            }), encoding="utf-8")

            # Passes with repetitions=1
            res1 = check_benchmark_matrix(p, target_tasks=target, repetitions=1)
            self.assertTrue(res1["is_complete"])
            self.assertEqual(res1["completed_tasks_count"], 1)

            # Fails with repetitions=2 because rep 2 is missing
            res2 = check_benchmark_matrix(p, target_tasks=target, repetitions=2)
            self.assertFalse(res2["is_complete"])
            self.assertEqual(res2["completed_tasks_count"], 0)
            self.assertEqual(res2["completed_matrix_cells"], 3)
            self.assertEqual(res2["total_matrix_cells"], 6)

    def test_matrix_requires_all_policies(self):
        """Verify that a task missing a required policy is marked incomplete."""
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            target = [{"id": "task_a"}]
            (p / "task_a-live.json").write_text(json.dumps({
                "rows": [
                    {"condition": "resample", "repetition": 1, "success": True, "heldout": {"passed": True}, "history": []},
                    {"condition": "feedback", "repetition": 1, "success": True, "heldout": {"passed": True}, "history": []},
                ],
                "pending": {}
            }), encoding="utf-8")
            res = check_benchmark_matrix(p, target_tasks=target, repetitions=1)
            self.assertFalse(res["is_complete"])
            self.assertIn("task_a", res["incomplete_task_ids"])

    def test_matrix_rejects_malformed_incomplete_row(self):
        """Finding 1: Verify check_benchmark_matrix rejects incomplete rows lacking terminal outcomes."""
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            target = [{"id": "task_stub"}]
            # Row has condition and repetition but lacks success and heldout
            (p / "task_stub-live.json").write_text(json.dumps({
                "rows": [
                    {"condition": "resample", "repetition": 1},
                    {"condition": "feedback", "repetition": 1},
                    {"condition": "counterfactual", "repetition": 1},
                ],
                "pending": {}
            }), encoding="utf-8")
            res = check_benchmark_matrix(p, target_tasks=target, repetitions=1)
            self.assertFalse(res["is_complete"])
            self.assertEqual(res["completed_tasks_count"], 0)
            self.assertEqual(res["completed_matrix_cells"], 0)

    def test_matrix_rejects_contradicting_key(self):
        """Finding 1: Reject row where condition or repetition contradicts row['key']."""
        bad_row = {
            "key": "2:feedback",
            "condition": "resample",
            "repetition": 1,
            "success": True,
            "heldout": {"passed": True},
            "history": [],
        }
        self.assertFalse(is_valid_evaluation_row(bad_row, "resample", 1))

    def test_matrix_supports_counterfactual_replay_policy(self):
        """Finding 2: Matrix properly recognizes and requires counterfactual_replay when configured."""
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            target = [{"id": "t_rep"}]
            (p / "t_rep-live.json").write_text(json.dumps({
                "rows": [
                    {"condition": "resample", "repetition": 1, "success": True, "heldout": {"passed": True}, "history": []},
                    {"condition": "feedback", "repetition": 1, "success": True, "heldout": {"passed": True}, "history": []},
                    {"condition": "counterfactual_replay", "repetition": 1, "success": True, "heldout": {"passed": True}, "history": []},
                ],
                "pending": {}
            }), encoding="utf-8")
            # Should be complete under replay policy set
            res = check_benchmark_matrix(
                p,
                target_tasks=target,
                repetitions=1,
                required_policies={"resample", "feedback", "counterfactual_replay"},
            )
            self.assertTrue(res["is_complete"])
            self.assertEqual(res["completed_tasks_count"], 1)

    def test_post_benchmark_pipeline_fails_closed_on_error(self):
        """Verify that run_post_benchmark_pipeline raises RuntimeError when a step fails."""
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            with patch("benchmarks.v18.autonomous_runner.summarize", side_effect=Exception("Disk full")):
                with self.assertRaises(RuntimeError) as ctx:
                    run_post_benchmark_pipeline(p, target_total=1)
                self.assertIn("Post-benchmark evidence pipeline failed", str(ctx.exception))
                self.assertIn("Disk full", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
