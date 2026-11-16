"""Offline provider rate-limit regression checks."""
import os
import unittest
from unittest.mock import patch, Mock

from codepilot.agent import LLMAPIError, _retry_delay, ask_model


class RateLimitTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"GROQ_API_KEY": "dummy-test-key", "CODEPILOT_PROVIDER": "groq"})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_retry_after_longer_than_cap_is_not_shortened(self):
        response = Mock(headers={"Retry-After": "120"})
        self.assertGreater(_retry_delay(response, 0), 120)

    @patch("codepilot.agent.time.sleep")
    @patch("codepilot.agent.requests.post")
    def test_long_retry_after_defers_without_retrying(self, post, sleep):
        post.return_value = Mock(status_code=429, headers={"Retry-After": "180"})
        with self.assertRaisesRegex(LLMAPIError, "HTTP 429"):
            ask_model([{"role": "user", "content": "test"}])
        self.assertEqual(post.call_count, 1)
        sleep.assert_not_called()

    @patch("codepilot.agent.time.sleep")
    @patch("codepilot.agent.requests.post")
    def test_short_retry_after_succeeds(self, post, sleep):
        limited = Mock(status_code=429, headers={"Retry-After": "2"})
        good = Mock(status_code=200)
        good.json.return_value = {"choices": [{"message": {"content": "valid"}}]}
        post.side_effect = [limited, good]
        self.assertEqual(ask_model([{"role": "user", "content": "test"}]), "valid")
        self.assertEqual(post.call_count, 2)
        sleep.assert_called_once()


if __name__ == "__main__":
    unittest.main()
