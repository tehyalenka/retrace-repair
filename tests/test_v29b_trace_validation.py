"""Reject invalid checkpoint traces before evaluation or provider access."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from benchmarks.v18 import checkpointed_three_arm as cp
from benchmarks.v18 import record_replay as replay


class TraceValidationTests(unittest.TestCase):

    def test_rejects_zero_public_tests(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            trace_path = root / "trace.json"
            output_path = root / "report.json"

            with patch.object(
                replay.agent_module, "ask_model",
                return_value='{"reasoning_summary":"test","edits":[]}'
            ):
                replay.capture("offline", "bugfix", trace_path)

            trace = json.loads(trace_path.read_text(encoding="utf-8"))
            trace["first_attempt"] = {
                "failure_category": "test_failure",
                "failure_stage": "smoke_tests",
                "tests_run": 0,
                "output": "No tests discovered",
            }
            trace_path.write_text(json.dumps(trace), encoding="utf-8")

            with patch.object(cp, "experiment_provenance") as provenance:
                with patch.object(replay.agent_module, "ask_model") as model:
                    with self.assertRaisesRegex(
                        ValueError, "genuine public-test failure"
                    ):
                        cp.evaluate(
                            trace_path,
                            output_path,
                            offline=True,
                            attempts=2,
                        )

                    provenance.assert_not_called()
                    model.assert_not_called()
                    self.assertFalse(output_path.exists())


if __name__ == "__main__":
    unittest.main()
