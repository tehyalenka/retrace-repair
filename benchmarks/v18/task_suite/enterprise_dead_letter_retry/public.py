import unittest
from retry_dlq import RetryDispatcher, MockDLQSink, RetryableError, NonRetryableError

class Public(unittest.TestCase):
    def test_transient_failure_retries_and_succeeds(self):
        dispatcher = RetryDispatcher(max_attempts=3)
        sink = MockDLQSink()
        calls = [0]

        def flaky_worker(p):
            calls[0] += 1
            if calls[0] < 2:
                raise RetryableError("temporary network blip")
            return f"processed-{p['id']}"

        res = dispatcher.execute(flaky_worker, {"id": 10}, sink)
        self.assertEqual(res, "processed-10")
        self.assertEqual(calls[0], 2)
        self.assertEqual(len(sink.records), 0)

    def test_non_retryable_error_routes_to_dlq_immediately(self):
        dispatcher = RetryDispatcher(max_attempts=3)
        sink = MockDLQSink()
        calls = [0]

        def fatal_worker(p):
            calls[0] += 1
            raise NonRetryableError("malformed schema 400")

        with self.assertRaises(NonRetryableError):
            dispatcher.execute(fatal_worker, {"id": "bad"}, sink)

        # Fatal error must NOT retry: only 1 attempt
        self.assertEqual(calls[0], 1)
        # Must be logged to DLQ sink
        self.assertEqual(len(sink.records), 1)
        self.assertEqual(sink.records[0]["attempts"], 1)
        self.assertIn("malformed schema 400", sink.records[0]["error"])
