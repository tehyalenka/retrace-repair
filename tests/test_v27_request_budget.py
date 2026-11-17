"""Offline tests for scoped model HTTP request budgets."""

import unittest
from unittest.mock import Mock, patch

from codepilot.agent import (
    ask_model,
    ModelRequestAccounting,
    ModelRequestBudgetExceeded,
    LLMAPIError,
)


def response(status=200):
    result = Mock()
    result.status_code = status
    result.headers = {"Retry-After": "0"}
    result.json.return_value = {
        "choices": [{"message": {"content": "{}"}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }
    return result


class RequestBudgetTests(unittest.TestCase):

    def setUp(self):
        provider = patch(
            "codepilot.agent.provider_config",
            return_value=("test-key", "test-model", "https://example.com"),
        )
        provider.start()
        self.addCleanup(provider.stop)

        env = patch.dict(
            "os.environ",
            {"CODEPILOT_MAX_RETRIES": "0"},
        )
        env.start()
        self.addCleanup(env.stop)

    def test_invalid_budgets_rejected(self):
        for value in (-1, 1.5, True, "2"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    ModelRequestAccounting(max_http_requests=value)

    @patch("codepilot.agent.requests.post")
    def test_zero_budget_blocks_all_requests(self, post):
        with ModelRequestAccounting(max_http_requests=0) as accounting:
            with self.assertRaises(ModelRequestBudgetExceeded):
                ask_model([{"role": "user", "content": "test"}])

        post.assert_not_called()
        self.assertEqual(accounting.http_requests, 0)

    @patch("codepilot.agent.requests.post")
    def test_exact_budget_enforced(self, post):
        post.return_value = response()

        with ModelRequestAccounting(max_http_requests=2) as accounting:
            ask_model([{"role": "user", "content": "one"}])
            ask_model([{"role": "user", "content": "two"}])

            with self.assertRaises(ModelRequestBudgetExceeded):
                ask_model([{"role": "user", "content": "three"}])

        self.assertEqual(post.call_count, 2)
        self.assertEqual(accounting.http_requests, 2)

    @patch("codepilot.agent.time.sleep")
    @patch("codepilot.agent.requests.post")
    def test_retries_consume_budget(self, post, sleep):
        post.side_effect = [
            response(503),
            response(503),
            response(200),
        ]

        with patch.dict(
            "os.environ",
            {"CODEPILOT_MAX_RETRIES": "3"},
        ):
            with ModelRequestAccounting(max_http_requests=2) as accounting:
                with self.assertRaises(ModelRequestBudgetExceeded):
                    ask_model([{"role": "user", "content": "retry"}])

        self.assertEqual(post.call_count, 2)
        self.assertEqual(accounting.http_requests, 2)
        self.assertEqual(accounting.http_failures, 2)

    @patch("codepilot.agent.requests.post")
    def test_unlimited_default_preserved(self, post):
        post.return_value = response()

        with ModelRequestAccounting() as accounting:
            for _ in range(3):
                ask_model([{"role": "user", "content": "test"}])

        self.assertEqual(post.call_count, 3)
        self.assertEqual(accounting.http_requests, 3)


if __name__ == "__main__":
    unittest.main()
