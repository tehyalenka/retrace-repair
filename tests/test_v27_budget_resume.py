"""Offline regression tests for durable HTTP budgets across interruptions."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import requests

from benchmarks.v18 import record_replay as base
from benchmarks.v18 import checkpointed_three_arm as cp


class BudgetResumeTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.trace = self.root / "trace.json"
        self.output = self.root / "report.json"
        base.capture("offline", "bugfix", self.trace)

        # Allow the scripted initial completion but force live continuations.
        trace_data = json.loads(self.trace.read_text())
        trace_data["mode"] = "live"
        self.trace.write_text(json.dumps(trace_data))

        # The benchmark requires a matching repository/task fingerprint.
        # Patch task_setup to supply the original offline fixture.
        self.original_setup = base.task_setup

        def setup(mode, case, temp):
            return self.original_setup("offline", case, temp)

        self.setup_patch = patch.object(base, "task_setup", side_effect=setup)
        self.setup_patch.start()
        self.addCleanup(self.setup_patch.stop)

        self.provider_patch = patch(
            "codepilot.agent.provider_config",
            return_value=("test-key", "test-model", "https://example.com"),
        )
        self.provider_patch.start()
        self.addCleanup(self.provider_patch.stop)

        self.env_patch = patch.dict(
            "os.environ",
            {"CODEPILOT_MAX_RETRIES": "1"},
        )
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)

    def test_timeout_reservations_survive_resume(self):
        with patch(
            "codepilot.agent.requests.post",
            side_effect=requests.Timeout("simulated timeout"),
        ) as post:
            with patch("codepilot.agent.time.sleep"):
                with self.assertRaises(cp.ProviderBlocked):
                    cp.evaluate(
                        self.trace,
                        self.output,
                        max_http_requests_per_arm=3,
                        attempts=2,
                    )

        self.assertEqual(post.call_count, 2)

        checkpoint = json.loads(self.output.read_text())
        self.assertEqual(
            checkpoint["request_reservations"]["1:resample"], 2
        )

        # On resume, only one request remains.
        with patch(
            "codepilot.agent.requests.post",
            side_effect=requests.Timeout("simulated timeout"),
        ) as post:
            with patch("codepilot.agent.time.sleep"):
                with self.assertRaises(cp.BenchmarkBudgetExceeded):
                    cp.evaluate(
                        self.trace,
                        self.output,
                        max_http_requests_per_arm=3,
                        attempts=2,
                    )

        self.assertEqual(post.call_count, 1)

        checkpoint = json.loads(self.output.read_text())
        self.assertEqual(
            checkpoint["request_reservations"]["1:resample"], 3
        )

    def test_failed_checkpoint_write_blocks_http(self):
        original_write = cp._write

        def fail_on_reservation(path, value):
            if value.get("request_reservations", {}).get("1:resample", 0):
                raise OSError("simulated checkpoint write failure")
            return original_write(path, value)

        with patch.object(cp, "_write", side_effect=fail_on_reservation):
            with patch("codepilot.agent.requests.post") as post:
                with self.assertRaises(OSError):
                    cp.evaluate(
                        self.trace,
                        self.output,
                        max_http_requests_per_arm=3,
                        attempts=2,
                    )

                post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
