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

    def test_checkpointed_completion_replayed(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace = Path(tmp) / "trace.json"
            output = Path(tmp) / "results.json"
            record_replay.capture("offline", "bugfix", trace)
            with patch("benchmarks.v18.checkpointed_three_arm._write", wraps=__import__("benchmarks.v18.checkpointed_three_arm", fromlist=["_write"])._write) as write:
                evaluate(trace, output, offline=True)
                self.assertGreater(write.call_count, 3)
