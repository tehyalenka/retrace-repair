"""Offline tests for checkpoint model-provenance enforcement."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from benchmarks.v18 import checkpointed_three_arm as cp
from benchmarks.v18 import record_replay as base


class CheckpointProvenanceTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.trace = self.root / "trace.json"
        self.output = self.root / "checkpoint.json"
        base.capture("offline", "bugfix", self.trace)

    def test_offline_checkpoint_preserves_compatibility(self):
        report = cp.evaluate(
            self.trace,
            self.output,
            offline=True,
            attempts=2,
        )
        self.assertNotIn("model_provenance", report["settings"])

        resumed = cp.evaluate(
            self.trace,
            self.output,
            offline=True,
            attempts=2,
        )
        self.assertEqual(report["settings"], resumed["settings"])

    def test_live_checkpoint_records_model_provenance(self):
        original = cp._write

        def interrupt_after_initial_write(path, value):
            original(path, value)
            if value.get("settings", {}).get("model_provenance"):
                raise RuntimeError("stop before live provider request")

        with patch.object(cp, "_write", side_effect=interrupt_after_initial_write):
            with patch.dict(
                "os.environ",
                {"CODEPILOT_PROVIDER": "groq"},
                clear=True,
            ):
                with self.assertRaises(RuntimeError):
                    cp.evaluate(
                        self.trace,
                        self.output,
                        offline=False,
                        attempts=2,
                    )

        report = json.loads(self.output.read_text())
        provenance = report["settings"]["model_provenance"]
        self.assertEqual(provenance["provider"], "groq")
        self.assertEqual(provenance["model"], "openai/gpt-oss-120b")
        self.assertNotIn("api_key", provenance)

    def test_changed_model_rejected_before_provider_request(self):
        with patch.dict("os.environ", {}, clear=True):
            original = cp._write

            def interrupt(path, value):
                original(path, value)
                raise RuntimeError("stop before provider request")

            with patch.object(cp, "_write", side_effect=interrupt):
                with self.assertRaises(RuntimeError):
                    cp.evaluate(
                        self.trace,
                        self.output,
                        offline=False,
                        attempts=2,
                    )

        with patch.dict(
            "os.environ",
            {"CODEPILOT_MODEL": "different-model"},
            clear=True,
        ):
            with patch("codepilot.agent.requests.post") as post:
                with self.assertRaisesRegex(
                    ValueError,
                    "Checkpoint settings",
                ):
                    cp.evaluate(
                        self.trace,
                        self.output,
                        offline=False,
                        attempts=2,
                    )
                post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
