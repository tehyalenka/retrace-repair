import unittest
from consumer import IdempotentConsumer, ConflictingPayloadError

class Heldout(unittest.TestCase):
    def test_handler_failure_allows_subsequent_retry(self):
        consumer = IdempotentConsumer(window_seconds=60.0)
        attempts = [0]
        def flaky_handler(p):
            attempts[0] += 1
            if attempts[0] == 1:
                raise ConnectionError("transient network failure")
            return "recovered"

        # First attempt raises exception
        with self.assertRaises(ConnectionError):
            consumer.process("evt-fail", {"x": 1}, flaky_handler, now=100.0)

        # Retry must execute handler and succeed
        res = consumer.process("evt-fail", {"x": 1}, flaky_handler, now=101.0)
        self.assertEqual(res, "recovered")
        self.assertEqual(attempts[0], 2)

    def test_eviction_after_window_expires(self):
        consumer = IdempotentConsumer(window_seconds=30.0)
        calls = [0]
        def handler(p):
            calls[0] += 1
            return calls[0]

        consumer.process("evt-old", {"a": 1}, handler, now=100.0)
        self.assertEqual(calls[0], 1)

        # After window expires (100 + 35 = 135)
        consumer.process("evt-old", {"a": 1}, handler, now=135.0)
        self.assertEqual(calls[0], 2)

    def test_invalid_parameters_raise_value_error(self):
        consumer = IdempotentConsumer(window_seconds=10.0)
        with self.assertRaises(ValueError):
            consumer.process("", {"a": 1}, lambda p: 1)
        with self.assertRaises(ValueError):
            consumer.process("e1", {"a": 1}, "not a func")
        with self.assertRaises(ValueError):
            IdempotentConsumer(window_seconds=-5)
