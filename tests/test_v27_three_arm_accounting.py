"""Offline tests for RETRACE three-arm accounting integration."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from benchmarks.v18 import record_replay as base
from benchmarks.v18.checkpointed_three_arm import evaluate


class ThreeArmAccountingTests(unittest.TestCase):

    def test_offline_replay_has_no_fresh_provider_requests(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            trace = root / "trace.json"
            report_path = root / "report.json"

            base.capture("offline", "bugfix", trace)

            with patch(
                "codepilot.agent.requests.post",
                side_effect=AssertionError(
                    "Offline benchmark attempted a provider request"
                ),
            ):
                report = evaluate(
                    trace,
                    report_path,
                    offline=True,
                    repetitions=1,
                    attempts=2,
                )

            self.assertEqual(len(report["rows"]), 3)

            for row in report["rows"]:
                with self.subTest(condition=row["condition"]):
                    origins = row["completion_origins"]
                    accounting = row["request_accounting"]

                    self.assertEqual(origins["captured_initial"], 1)
                    self.assertEqual(origins["live"], 0)
                    self.assertEqual(
                        accounting["http_requests"], 0
                    )
                    self.assertEqual(
                        accounting["logical_calls"], 0
                    )
                    self.assertEqual(
                        accounting["usage_reports"], 0
                    )
                    self.assertGreaterEqual(
                        origins["scripted"], 1
                    )

    def test_completed_report_is_resumable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            trace = root / "trace.json"
            report_path = root / "report.json"

            base.capture("offline", "bugfix", trace)

            first = evaluate(
                trace,
                report_path,
                offline=True,
                repetitions=1,
                attempts=2,
            )

            second = evaluate(
                trace,
                report_path,
                offline=True,
                repetitions=1,
                attempts=2,
            )

            self.assertEqual(first, second)
            self.assertEqual(len(second["rows"]), 3)


if __name__ == "__main__":
    unittest.main()
