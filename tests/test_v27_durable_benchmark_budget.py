"""Offline tests for checkpointed HTTP request budgets."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from benchmarks.v18 import record_replay as base
from benchmarks.v18 import checkpointed_three_arm as cp
from codepilot.agent import (
    ModelRequestAccounting,
    ModelRequestBudgetExceeded,
)


class DurableBenchmarkBudgetTests(unittest.TestCase):

    def test_offline_budget_zero_requires_no_http(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            trace = root / "trace.json"
            output = root / "report.json"
            base.capture("offline", "bugfix", trace)

            with patch(
                "codepilot.agent.requests.post",
                side_effect=AssertionError("Unexpected HTTP request"),
            ):
                result = cp.evaluate(
                    trace, output,
                    offline=True,
                    attempts=2,
                    max_http_requests_per_arm=0,
                )

            self.assertEqual(len(result["rows"]), 3)
            self.assertEqual(result["settings"]["max_http_requests_per_arm"], 0)
            self.assertTrue(all(
                row["request_accounting"]["http_requests"] == 0
                for row in result["rows"]
            ))

    def test_budget_setting_is_immutable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            trace = root / "trace.json"
            output = root / "report.json"
            base.capture("offline", "bugfix", trace)

            cp.evaluate(
                trace, output,
                offline=True,
                attempts=2,
                max_http_requests_per_arm=2,
            )

            with self.assertRaises(ValueError):
                cp.evaluate(
                    trace, output,
                    offline=True,
                    attempts=2,
                    max_http_requests_per_arm=3,
                )

    def test_completed_checkpoint_resumes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            trace = root / "trace.json"
            output = root / "report.json"
            base.capture("offline", "bugfix", trace)

            first = cp.evaluate(
                trace, output,
                offline=True,
                attempts=2,
                max_http_requests_per_arm=1,
            )
            second = cp.evaluate(
                trace, output,
                offline=True,
                attempts=2,
                max_http_requests_per_arm=1,
            )
            self.assertEqual(first, second)

    def test_budget_exception_is_distinct(self):
        self.assertFalse(
            issubclass(cp.BenchmarkBudgetExceeded, cp.ProviderBlocked)
        )
        with self.assertRaises(ModelRequestBudgetExceeded):
            with ModelRequestAccounting(max_http_requests=0):
                from codepilot.agent import ask_model
                with patch(
                    "codepilot.agent.provider_config",
                    return_value=("key", "model", "https://example.com"),
                ):
                    ask_model([{"role": "user", "content": "test"}])

    def test_invalid_budget_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            trace = root / "trace.json"
            base.capture("offline", "bugfix", trace)

            for invalid in (-1, True, 1.5, "2"):
                with self.subTest(value=invalid):
                    with self.assertRaises(ValueError):
                        cp.evaluate(
                            trace, root / "report.json",
                            offline=True,
                            max_http_requests_per_arm=invalid,
                        )


if __name__ == "__main__":
    unittest.main()
