"""Offline tests for durable HTTP request reservation hooks."""

import unittest
from unittest.mock import Mock, patch

from codepilot.agent import (
    ask_model,
    ModelRequestAccounting,
    ModelRequestBudgetExceeded,
)


MESSAGES = [{"role": "user", "content": "test"}]


def successful_response():
    result = Mock()
    result.status_code = 200
    result.json.return_value = {
        "choices": [{"message": {"content": "{}"}}],
    }
    return result


class RequestReservationTests(unittest.TestCase):

    def setUp(self):
        provider = patch(
            "codepilot.agent.provider_config",
            return_value=("test-key", "test-model", "https://example.com"),
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
    def test_reservation_before_http_request(self, post):
        reserved = []

        def reserve(count):
            self.assertEqual(post.call_count, count - 1)
            reserved.append(count)

        post.return_value = successful_response()

        with ModelRequestAccounting(
            max_http_requests=2,
            on_request_reserved=reserve,
        ) as accounting:
            ask_model(MESSAGES)
            ask_model(MESSAGES)

        self.assertEqual(reserved, [1, 2])
        self.assertEqual(accounting.http_requests, 2)

    @patch("codepilot.agent.requests.post")
    def test_failed_reservation_blocks_http(self, post):
        def reserve(count):
            raise OSError("checkpoint unavailable")

        with ModelRequestAccounting(
            max_http_requests=1,
            on_request_reserved=reserve,
        ):
            with self.assertRaises(OSError):
                ask_model(MESSAGES)

        post.assert_not_called()

    @patch("codepilot.agent.requests.post")
    def test_budget_checked_before_reservation(self, post):
        reserved = []

        with ModelRequestAccounting(
            max_http_requests=0,
            on_request_reserved=reserved.append,
        ):
            with self.assertRaises(ModelRequestBudgetExceeded):
                ask_model(MESSAGES)

        self.assertEqual(reserved, [])
        post.assert_not_called()

    def test_invalid_reservation_callback_rejected(self):
        with self.assertRaises(ValueError):
            ModelRequestAccounting(on_request_reserved="not callable")


if __name__ == "__main__":
    unittest.main()
