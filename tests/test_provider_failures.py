import os
import unittest
from unittest.mock import Mock, patch

import requests

from codepilot.agent import ask_model, LLMAPIError


MESSAGES = [{"role": "user", "content": "Hello"}]


def response_with_status(status, retry_after=None):
    response = Mock()
    response.status_code = status
    response.headers = {}

    if retry_after is not None:
        response.headers["Retry-After"] = str(retry_after)

    response.json.return_value = {
        "error": {"message": "Provider temporarily unavailable"}
    }
    return response


class ProviderFailureTests(unittest.TestCase):

    def setUp(self):
        self.environment = patch.dict(
            os.environ,
            {
                "CODEPILOT_PROVIDER": "groq",
                "GROQ_API_KEY": "offline-test-key",
                "CODEPILOT_MAX_RETRIES": "0",
                "CODEPILOT_JSON_MODE": "0",
            },
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)

    @patch("codepilot.agent.requests.post")
    def test_rate_limit_without_retries(self, post):
        post.return_value = response_with_status(429, retry_after=1)

        with self.assertRaisesRegex(LLMAPIError, "HTTP 429"):
            ask_model(MESSAGES)

        self.assertEqual(post.call_count, 1)

    @patch("codepilot.agent.requests.post")
    def test_server_unavailable_without_retries(self, post):
        post.return_value = response_with_status(503)

        with self.assertRaisesRegex(LLMAPIError, "HTTP 503"):
            ask_model(MESSAGES)

        self.assertEqual(post.call_count, 1)

    @patch("codepilot.agent.requests.post")
    def test_timeout_without_retries(self, post):
        post.side_effect = requests.Timeout("Simulated timeout")

        with self.assertRaisesRegex(LLMAPIError, "connection failed"):
            ask_model(MESSAGES)

        self.assertEqual(post.call_count, 1)

    @patch("codepilot.agent.time.sleep")
    @patch("codepilot.agent.requests.post")
    def test_success_after_retry(self, post, sleep):
        os.environ["CODEPILOT_MAX_RETRIES"] = "1"

        success = Mock()
        success.status_code = 200
        success.json.return_value = {
            "choices": [
                {"message": {"content": '{"edits": []}'}}
            ]
        }

        post.side_effect = [
            response_with_status(503, retry_after=0),
            success,
        ]

        result = ask_model(MESSAGES)

        self.assertEqual(result, '{"edits": []}')
        self.assertEqual(post.call_count, 2)

    @patch("codepilot.agent.time.sleep")
    @patch("codepilot.agent.requests.post")
    def test_long_rate_limit_does_not_retry(self, post, sleep):
        os.environ["CODEPILOT_MAX_RETRIES"] = "3"

        post.return_value = response_with_status(
            429,
            retry_after=120,
        )

        with self.assertRaisesRegex(LLMAPIError, "resume later"):
            ask_model(MESSAGES)

        self.assertEqual(post.call_count, 1)
        sleep.assert_not_called()

    @patch("codepilot.agent.requests.post")
    def test_invalid_retry_configuration(self, post):
        os.environ["CODEPILOT_MAX_RETRIES"] = "11"

        with self.assertRaisesRegex(ValueError, "between 0 and 10"):
            ask_model(MESSAGES)

        post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
