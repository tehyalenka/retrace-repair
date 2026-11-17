"""Offline regression tests for configurable sampling temperature."""

import unittest
from unittest.mock import patch

from codepilot.agent import ask_model


class SamplingTests(unittest.TestCase):

    def setUp(self):
        self.provider = patch(
            "codepilot.agent.provider_config",
            return_value=(
                "test-key",
                "test-model",
                "https://example.com",
            ),
        )
        self.post = patch("codepilot.agent.requests.post")

        self.provider.start()
        self.mock_post = self.post.start()

        self.addCleanup(self.provider.stop)
        self.addCleanup(self.post.stop)

        self.mock_post.return_value.status_code = 200
        self.mock_post.return_value.json.return_value = {
            "choices": [
                {"message": {"content": "{}"}}
            ]
        }

    def test_default_temperature(self):
        with patch.dict(
            "os.environ",
            {"CODEPILOT_TEMPERATURE": "0"},
        ):
            ask_model([
                {"role": "user", "content": "test"}
            ])

        payload = self.mock_post.call_args.kwargs["json"]
        self.assertEqual(payload["temperature"], 0.0)

    def test_explicit_temperature_override(self):
        with patch.dict(
            "os.environ",
            {"CODEPILOT_TEMPERATURE": "0.2"},
        ):
            ask_model(
                [{"role": "user", "content": "test"}],
                temperature=0.7,
            )

        payload = self.mock_post.call_args.kwargs["json"]
        self.assertEqual(payload["temperature"], 0.7)

    def test_invalid_temperature_rejected(self):
        for value in (
            -0.1,
            2.1,
            "invalid",
            float("nan"),
            float("inf"),
        ):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    ask_model([], temperature=value)

        self.mock_post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
