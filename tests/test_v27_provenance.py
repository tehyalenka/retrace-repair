"""Offline tests for experiment provenance."""

import unittest
from unittest.mock import patch

from benchmarks.v18.provenance import experiment_provenance


class ExperimentProvenanceTests(unittest.TestCase):

    def test_offline_requires_no_provider(self):
        with patch.dict(
            "os.environ",
            {"CODEPILOT_PROVIDER": "invalid"},
        ):
            result = experiment_provenance(offline=True)

        self.assertEqual(result["execution"], "scripted_offline")
        self.assertIsNone(result["model"])

    def test_live_defaults(self):
        with patch.dict("os.environ", {}, clear=True):
            result = experiment_provenance()

        self.assertEqual(result["provider"], "groq")
        self.assertEqual(result["model"], "openai/gpt-oss-120b")
        self.assertEqual(result["temperature"], 0.0)
        self.assertEqual(result["max_retries"], 3)

    def test_explicit_model_configuration(self):
        with patch.dict(
            "os.environ",
            {
                "CODEPILOT_PROVIDER": "gemini",
                "CODEPILOT_MODEL": "custom-model",
                "CODEPILOT_TEMPERATURE": "0.7",
                "CODEPILOT_JSON_MODE": "1",
            },
            clear=True,
        ):
            result = experiment_provenance()

        self.assertEqual(result["provider"], "gemini")
        self.assertEqual(result["model"], "custom-model")
        self.assertEqual(result["temperature"], 0.7)
        self.assertTrue(result["json_mode"])

    def test_invalid_temperature(self):
        with patch.dict(
            "os.environ",
            {"CODEPILOT_TEMPERATURE": "3"},
            clear=True,
        ):
            with self.assertRaises(ValueError):
                experiment_provenance()

    def test_invalid_provider(self):
        with patch.dict(
            "os.environ",
            {"CODEPILOT_PROVIDER": "unknown"},
            clear=True,
        ):
            with self.assertRaises(ValueError):
                experiment_provenance()


if __name__ == "__main__":
    unittest.main()
