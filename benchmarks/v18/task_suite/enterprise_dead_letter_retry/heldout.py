import unittest
from retry_dlq import RetryDispatcher, MockDLQSink, RetryableError, NonRetryableError

class Heldout(unittest.TestCase):
    def test_exhausted_retries_route_to_dlq(self):
        dispatcher = RetryDispatcher(max_attempts=3)
        sink = MockDLQSink()
        calls = [0]

        def persistent_error(p):
            calls[0] += 1
            raise RetryableError("database down 503")

        with self.assertRaises(RetryableError):
            dispatcher.execute(persistent_error, {"item": "xyz"}, sink)

        self.assertEqual(calls[0], 3)
        self.assertEqual(len(sink.records), 1)
        self.assertEqual(sink.records[0]["attempts"], 3)
        self.assertEqual(sink.records[0]["payload"], {"item": "xyz"})

    def test_backoff_delay_calculation(self):
        dispatcher = RetryDispatcher(max_attempts=5, base_delay=0.1, max_delay=0.5)
        self.assertAlmostEqual(dispatcher.calculate_backoff(0), 0.0)
        # Attempt 1: 0.1 * 1 = 0.1
        self.assertAlmostEqual(dispatcher.calculate_backoff(1), 0.1)
        # Attempt 2: 0.1 * 2 = 0.2
        self.assertAlmostEqual(dispatcher.calculate_backoff(2), 0.2)
        # Attempt 3: 0.1 * 4 = 0.4
        self.assertAlmostEqual(dispatcher.calculate_backoff(3), 0.4)
        # Attempt 4: 0.1 * 8 = 0.8 clamped to 0.5
        self.assertAlmostEqual(dispatcher.calculate_backoff(4), 0.5)

    def test_invalid_parameters_raise_value_error(self):
        with self.assertRaises(ValueError):
            RetryDispatcher(max_attempts=0)
        with self.assertRaises(ValueError):
            RetryDispatcher(base_delay=-1.0)
        with self.assertRaises(ValueError):
            RetryDispatcher(base_delay=2.0, max_delay=1.0)

        dispatcher = RetryDispatcher()
        with self.assertRaises(ValueError):
            dispatcher.execute("not callable", {}, MockDLQSink())
        with self.assertRaises(ValueError):
            dispatcher.execute(lambda p: 1, {}, None)
