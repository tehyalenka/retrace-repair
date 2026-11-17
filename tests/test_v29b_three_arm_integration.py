"""Offline integration test for real synthetic three-arm replay."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from benchmarks.v18 import checkpointed_three_arm as cp
from benchmarks.v18 import record_replay as replay
from benchmarks.v18.task_suite_runner import ROOT, fixture, tasks


class ThreeArmIntegrationTests(unittest.TestCase):

    def test_real_fixture_capture_and_three_arm_replay(self):
        item = next(x for x in tasks() if x["id"] == "clamp_bounds")
        public = (ROOT / item["public_verifier"]).read_text(encoding="utf-8")
        heldout = (ROOT / item["heldout_verifier"]).read_text(encoding="utf-8")

        def edit(content):
            return json.dumps({
                "reasoning_summary": "Deterministic offline integration test",
                "edits": [{
                    "path": "calc.py",
                    "operation": "modify",
                    "content": content,
                }],
            })

        failing = edit("def clamp(x, lo, hi):\n    return min(x, hi)\n")
        repaired = edit(
            "def clamp(x, lo, hi):\n"
            "    return max(lo, min(x, hi))\n"
        )

        def setup(mode, case, temp):
            self.assertEqual(mode, "live")
            self.assertEqual(case, "clamp_bounds")
            repo = fixture(item, Path(temp) / "repo")
            return repo, item["task"], public

        with tempfile.TemporaryDirectory() as tmp:
            trace_path = Path(tmp) / "capture.json"
            report_path = Path(tmp) / "report.json"

            with patch.object(replay, "task_setup", side_effect=setup):
                with patch.object(
                    replay.agent_module, "ask_model", return_value=failing
                ):
                    trace = replay.capture(
                        "live", "clamp_bounds", trace_path
                    )

                first = trace["first_attempt"]
                self.assertEqual(first["failure_category"], "test_failure")
                self.assertGreaterEqual(first["tests_run"], 1)
                self.assertEqual(first["failure_stage"], "smoke_tests")

                # Mock only fresh continuations. Captured first edits are
                # replayed by the checkpoint evaluator itself.
                with patch.object(
                    replay.agent_module,
                    "ask_model",
                    return_value=repaired,
                ) as model:
                    with patch(
                        "codepilot.agent.requests.post",
                        side_effect=AssertionError("Network request forbidden"),
                    ):
                        report = cp.evaluate(
                            trace_path,
                            report_path,
                            offline=False,
                            repetitions=1,
                            attempts=2,
                            heldout_verification=heldout,
                        )

                    self.assertEqual(model.call_count, 3)

            rows = report["rows"]
            self.assertEqual(len(rows), 3)

            self.assertEqual(
                {row["condition"] for row in rows},
                {"resample", "feedback", "counterfactual"},
            )

            for row in rows:
                self.assertTrue(row["success"], row["condition"])
                self.assertTrue(
                    row["heldout"]["passed"], row["condition"]
                )
                self.assertGreaterEqual(
                    row["history"][0]["tests_run"], 1
                )
                self.assertEqual(
                    row["history"][0]["failure_category"],
                    "test_failure",
                )
                self.assertEqual(
                    row["completion_origins"]["captured_initial"], 1
                )

            self.assertTrue(report_path.is_file())


    def test_replayed_first_attempt_without_tests_is_rejected(self):
        """A replayed test_failure must represent an executed public test."""
        import tempfile
        from unittest.mock import patch

        from benchmarks.v18 import checkpointed_three_arm as cp
        from benchmarks.v18 import record_replay as replay

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            trace_path = root / "trace.json"
            report_path = root / "report.json"

            replay.capture("offline", "bugfix", trace_path)

            def invalid_agent(*args, **kwargs):
                return {
                    "success": False,
                    "history": [{
                        "failure_category": "test_failure",
                        "failure_stage": "smoke_tests",
                        "tests_run": 0,
                        "output": "No tests discovered",
                    }],
                }

            with patch.object(
                replay.agent_module, "run_agent",
                side_effect=invalid_agent,
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "public-test failure was not genuinely reproduced",
                ):
                    cp.evaluate(
                        trace_path,
                        report_path,
                        offline=True,
                        attempts=2,
                    )

            self.assertFalse(
                any(
                    row.get("success")
                    for row in (
                        __import__("json").loads(
                            report_path.read_text(encoding="utf-8")
                        ).get("rows", [])
                        if report_path.exists()
                        else []
                    )
                )
            )


if __name__ == "__main__":
    unittest.main()
