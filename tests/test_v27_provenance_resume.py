"""Verify immutable model configuration across checkpoint resumes."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from benchmarks.v18 import checkpointed_three_arm as cp
from benchmarks.v18 import record_replay as base


class ProvenanceResumeTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.trace = Path(self.tmp.name) / "trace.json"
        self.output = Path(self.tmp.name) / "checkpoint.json"

        base.capture("offline", "bugfix", self.trace)

        original_write = cp._write

        def interrupt(path, value):
            original_write(path, value)
            raise RuntimeError("simulated interruption")

        with patch.dict("os.environ", {}, clear=True):
            with patch.object(cp, "_write", side_effect=interrupt):
                with self.assertRaisesRegex(RuntimeError, "simulated interruption"):
                    cp.evaluate(
                        self.trace,
                        self.output,
                        offline=False,
                        attempts=2,
                    )

        self.assertIn(
            "model_provenance",
            json.loads(self.output.read_text())["settings"],
        )

    def assert_configuration_rejected(self, overrides):
        with patch.dict("os.environ", overrides, clear=True):
            with patch("codepilot.agent.requests.post") as post:
                with self.assertRaisesRegex(ValueError, "Checkpoint settings"):
                    cp.evaluate(
                        self.trace,
                        self.output,
                        offline=False,
                        attempts=2,
                    )
                post.assert_not_called()

    def test_temperature_change_rejected(self):
        self.assert_configuration_rejected(
            {"CODEPILOT_TEMPERATURE": "0.7"}
        )

    def test_http_retry_change_rejected(self):
        self.assert_configuration_rejected(
            {"CODEPILOT_MAX_RETRIES": "1"}
        )

    def test_format_retry_change_rejected(self):
        self.assert_configuration_rejected(
            {"CODEPILOT_FORMAT_RETRIES": "1"}
        )

    def test_json_mode_change_rejected(self):
        self.assert_configuration_rejected(
            {"CODEPILOT_JSON_MODE": "1"}
        )


if __name__ == "__main__":
    unittest.main()
