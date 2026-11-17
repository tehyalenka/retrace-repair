"""Offline regression tests for provider request accounting."""

import unittest
from unittest.mock import Mock, patch

import requests

from codepilot.agent import (
    ask_model,
    LLMAPIError,
    ModelRequestAccounting,
)

MESSAGES = [{"role": "user", "content": "test"}]


def success_response(with_usage=True):
    response = Mock()
    response.status_code = 200
    response.json.return_value = {
        "choices": [{"message": {"content": "{}"}}],
    }
    if with_usage:
        response.json.return_value["usage"] = {
            "prompt_tokens": 12,
            "completion_tokens": 8,
        }
    return response


class RequestAccountingTests(unittest.TestCase):

    def setUp(self):
        provider = patch(
            "codepilot.agent.provider_config",
            return_value=(
                "test-key", "test-model", "https://example.com"
            ),
        )
        provider.start()
        self.addCleanup(provider.stop)

        environment = patch.dict(
            "os.environ",
            {"CODEPILOT_MAX_RETRIES": "0"},
        )
        environment.start()
        self.addCleanup(environment.stop)

    @patch("codepilot.agent.requests.post")
    def test_success_and_token_usage(self, post):
        post.return_value = success_response()

        with ModelRequestAccounting() as accounting:
            self.assertEqual(ask_model(MESSAGES), "{}")

        self.assertEqual(accounting.snapshot(), {
            "logical_calls": 1,
            "http_requests": 1,
            "http_failures": 0,
            "prompt_tokens": 12,
            "completion_tokens": 8,
            "usage_reports": 1,
        })

    @patch("codepilot.agent.time.sleep")
    @patch("codepilot.agent.requests.post")
    def test_retry_accounting(self, post, sleep):
        failed = Mock()
        failed.status_code = 503
        failed.headers = {"Retry-After": "0"}

        post.side_effect = [
            failed,
            success_response(),
        ]

        with patch.dict(
            "os.environ",
            {"CODEPILOT_MAX_RETRIES": "1"},
        ):
            with ModelRequestAccounting() as accounting:
                self.assertEqual(ask_model(MESSAGES), "{}")

        self.assertEqual(accounting.logical_calls, 1)
        self.assertEqual(accounting.http_requests, 2)
        self.assertEqual(accounting.http_failures, 1)
        self.assertEqual(accounting.usage_reports, 1)

    @patch("codepilot.agent.requests.post")
    def test_timeout_accounting(self, post):
        post.side_effect = requests.Timeout("offline timeout")

        with ModelRequestAccounting() as accounting:
            with self.assertRaises(LLMAPIError):
                ask_model(MESSAGES)

        self.assertEqual(accounting.logical_calls, 1)
        self.assertEqual(accounting.http_requests, 1)
        self.assertEqual(accounting.http_failures, 1)

    @patch("codepilot.agent.requests.post")
    def test_separate_experiments(self, post):
        post.return_value = success_response()

        with ModelRequestAccounting() as first:
            ask_model(MESSAGES)

        with ModelRequestAccounting() as second:
            ask_model(MESSAGES)
            ask_model(MESSAGES)

        self.assertEqual(first.logical_calls, 1)
        self.assertEqual(second.logical_calls, 2)
        self.assertEqual(second.http_requests, 2)

    @patch("codepilot.agent.requests.post")
    def test_missing_usage_not_invented(self, post):
        post.return_value = success_response(with_usage=False)

        with ModelRequestAccounting() as accounting:
            ask_model(MESSAGES)

        self.assertEqual(accounting.http_requests, 1)
        self.assertEqual(accounting.usage_reports, 0)
        self.assertEqual(accounting.prompt_tokens, 0)
        self.assertEqual(accounting.completion_tokens, 0)

    @patch("codepilot.agent.requests.post")
    def test_nested_accounting(self, post):
        post.return_value = success_response()

        with ModelRequestAccounting() as outer:
            ask_model(MESSAGES)

            with ModelRequestAccounting() as inner:
                ask_model(MESSAGES)

            ask_model(MESSAGES)

        self.assertEqual(outer.logical_calls, 2)
        self.assertEqual(inner.logical_calls, 1)


if __name__ == "__main__":
    unittest.main()
