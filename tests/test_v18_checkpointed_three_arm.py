import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from benchmarks.v18 import record_replay
from benchmarks.v18.checkpointed_three_arm import evaluate


class CheckpointedThreeArmTests(unittest.TestCase):
    def test_offline_three_arms_and_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace = Path(tmp) / "trace.json"
            output = Path(tmp) / "results.json"
            record_replay.capture("offline", "bugfix", trace)
            result = evaluate(trace, output, offline=True, repetitions=1)
            self.assertEqual(len(result["rows"]), 3)
            self.assertEqual(len({r["key"] for r in result["rows"]}), 3)
            self.assertTrue(all(r["success"] for r in result["rows"]))
            self.assertTrue(all(r["live_calls"] == 0 for r in result["rows"]))
            again = evaluate(trace, output, offline=True, repetitions=1)
            self.assertEqual(len(again["rows"]), 3)

    def test_changed_settings_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace = Path(tmp) / "trace.json"
            output = Path(tmp) / "results.json"
            record_replay.capture("offline", "bugfix", trace)
            evaluate(trace, output, offline=True)
            with self.assertRaises(ValueError):
                evaluate(trace, output, offline=True, attempts=4)

    def test_changed_counterfactual_policy_rejected(self):
        """Finding 1 (Seventh Audit): Checkpoint rejects resume if counterfactual_policy changes."""
        with tempfile.TemporaryDirectory() as tmp:
            trace = Path(tmp) / "trace.json"
            output = Path(tmp) / "results.json"
            record_replay.capture("offline", "bugfix", trace)
            evaluate(trace, output, offline=True, counterfactual_policy="counterfactual")
            with self.assertRaises(ValueError) as ctx:
                evaluate(trace, output, offline=True, counterfactual_policy="counterfactual_replay")
            self.assertIn("Checkpoint settings or captured trace changed", str(ctx.exception))

    def test_checkpointed_completion_replayed(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace = Path(tmp) / "trace.json"
            output = Path(tmp) / "results.json"
            record_replay.capture("offline", "bugfix", trace)
            with patch("benchmarks.v18.checkpointed_three_arm._write", wraps=__import__("benchmarks.v18.checkpointed_three_arm", fromlist=["_write"])._write) as write:
                evaluate(trace, output, offline=True)
                self.assertGreater(write.call_count, 3)

    def test_checkpointed_counterfactual_replay_offline_execution(self):
        """Verify checkpointed three-arm execution with counterfactual_replay in offline mode."""
        with tempfile.TemporaryDirectory() as tmp:
            trace = Path(tmp) / "trace.json"
            output = Path(tmp) / "results.json"
            record_replay.capture("offline", "bugfix", trace)
            result = evaluate(trace, output, offline=True, counterfactual_policy="counterfactual_replay")
            self.assertEqual(result["settings"]["counterfactual_policy"], "counterfactual_replay")
            conditions = {row["condition"] for row in result["rows"]}
            self.assertEqual(conditions, {"resample", "feedback", "counterfactual_replay"})
            replay_row = next(r for r in result["rows"] if r["condition"] == "counterfactual_replay")
            self.assertTrue(replay_row["success"])
            # Attempt 1 must have reproduced failure, and Attempt 2 must have succeeded with replay
            history = replay_row["history"]
            self.assertEqual(len(history), 2)
            self.assertEqual(history[0]["failure_category"], "test_failure")
            self.assertTrue(history[1]["passed"])
            self.assertIn("replay", history[1])
