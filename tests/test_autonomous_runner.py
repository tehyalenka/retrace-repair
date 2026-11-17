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

            # create 1 completed file with valid non-empty terminal evaluation evidence
            t1 = p / "task1-live.json"
            t1.write_text(json.dumps({
                "rows": [
                    {"key": "1:resample", "condition": "resample", "repetition": 1, "success": True, "heldout": {"passed": True}, "history": [{"passed": True}]},
                    {"key": "1:feedback", "condition": "feedback", "repetition": 1, "success": True, "heldout": {"passed": True}, "history": [{"passed": True}]},
                    {"key": "1:counterfactual", "condition": "counterfactual", "repetition": 1, "success": True, "heldout": {"passed": True}, "history": [{"passed": True}]},
                ],
                "pending": {}
            }), encoding="utf-8")
            self.assertEqual(get_completed_tasks_count(p, 22), 1)

            # create incomplete file (with pending)
            t2 = p / "task2-live.json"
            t2.write_text(json.dumps({
                "rows": [
                    {"key": "1:resample", "condition": "resample", "repetition": 1, "success": True, "heldout": {"passed": True}, "history": [{"passed": True}]}
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
                    {"condition": "resample", "repetition": 1, "success": True, "heldout": {"passed": True}, "history": [{"passed": True}]},
                    {"condition": "feedback", "repetition": 1, "success": True, "heldout": {"passed": True}, "history": [{"passed": True}]},
                    {"condition": "counterfactual", "repetition": 1, "success": True, "heldout": {"passed": True}, "history": [{"passed": True}]},
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
                    {"condition": "resample", "repetition": 1, "success": True, "heldout": {"passed": True}, "history": [{"passed": True}]},
                    {"condition": "feedback", "repetition": 1, "success": True, "heldout": {"passed": True}, "history": [{"passed": True}]},
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

    def test_rejects_empty_evidence_containers(self):
        """Finding 1 & Audit 6: Empty containers must not pass terminal outcome validation."""
        empty_evidence_row = {
            "key": "1:resample",
            "condition": "resample",
            "repetition": 1,
            "success": True,
            "heldout": {"passed": True},
            "history": [],
            "calls": [],
            "request_accounting": {},
        }
        self.assertFalse(is_valid_evaluation_row(empty_evidence_row, "resample", 1))

        # Adding non-empty request accounting makes it valid
        valid_evidence_row = dict(empty_evidence_row)
        valid_evidence_row["request_accounting"] = {"prompt_tokens": 100, "completion_tokens": 50}
        self.assertTrue(is_valid_evaluation_row(valid_evidence_row, "resample", 1))

    def test_matrix_rejects_contradicting_key(self):
        """Reject row where condition or repetition contradicts row['key']."""
        bad_row = {
            "key": "2:feedback",
            "condition": "resample",
            "repetition": 1,
            "success": True,
            "heldout": {"passed": True},
            "history": [{"passed": True}],
        }
        self.assertFalse(is_valid_evaluation_row(bad_row, "resample", 1))

    def test_strict_policy_identity_no_substitution(self):
        """Audit 6 Research-Critical: counterfactual prompting CANNOT substitute for counterfactual_replay."""
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            target = [{"id": "t_strict"}]
            # Task only has 'counterfactual' (prompting)
            (p / "t_strict-live.json").write_text(json.dumps({
                "rows": [
                    {"condition": "resample", "repetition": 1, "success": True, "heldout": {"passed": True}, "history": [{"passed": True}]},
                    {"condition": "feedback", "repetition": 1, "success": True, "heldout": {"passed": True}, "history": [{"passed": True}]},
                    {"condition": "counterfactual", "repetition": 1, "success": True, "heldout": {"passed": True}, "history": [{"passed": True}]},
                ],
                "pending": {}
            }), encoding="utf-8")

            # Check against a replay experiment requiring 'counterfactual_replay'
            res = check_benchmark_matrix(
                p,
                target_tasks=target,
                repetitions=1,
                required_policies={"resample", "feedback", "counterfactual_replay"},
            )
            # Must NOT be complete because prompt condition cannot substitute for replay
            self.assertFalse(res["is_complete"])
            self.assertEqual(res["completed_tasks_count"], 0)
            self.assertEqual(res["completed_matrix_cells"], 2)  # only resample and feedback satisfied

    def test_matrix_supports_counterfactual_replay_policy(self):
        """Matrix properly completes when exact counterfactual_replay results are present."""
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            target = [{"id": "t_rep"}]
            (p / "t_rep-live.json").write_text(json.dumps({
                "rows": [
                    {"condition": "resample", "repetition": 1, "success": True, "heldout": {"passed": True}, "history": [{"passed": True}]},
                    {"condition": "feedback", "repetition": 1, "success": True, "heldout": {"passed": True}, "history": [{"passed": True}]},
                    {"condition": "counterfactual_replay", "repetition": 1, "success": True, "heldout": {"passed": True}, "history": [{"passed": True}]},
                ],
                "pending": {}
            }), encoding="utf-8")
            res = check_benchmark_matrix(
                p,
                target_tasks=target,
                repetitions=1,
                required_policies={"resample", "feedback", "counterfactual_replay"},
            )
            self.assertTrue(res["is_complete"])
            self.assertEqual(res["completed_tasks_count"], 1)
            self.assertEqual(res["completed_matrix_cells"], 3)

    def test_handles_malformed_repetition_without_crash(self):
        """Safely handle malformed repetition values without raising unhandled exceptions."""
        bad_rep_row = {
            "condition": "resample",
            "repetition": "invalid_not_an_int",
            "success": True,
            "heldout": {"passed": True},
            "history": [{"passed": True}],
        }
        self.assertFalse(is_valid_evaluation_row(bad_rep_row, "resample", 1))

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
