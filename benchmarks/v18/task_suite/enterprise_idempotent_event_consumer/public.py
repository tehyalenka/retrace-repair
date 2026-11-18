import unittest
from consumer import IdempotentConsumer, ConflictingPayloadError

class Public(unittest.TestCase):
    def test_idempotent_replay_returns_cached_result(self):
        consumer = IdempotentConsumer(window_seconds=60.0)
        call_count = [0]
        def handler(p):
            call_count[0] += 1
            return p["val"] * 2

        res1 = consumer.process("evt-1", {"val": 10}, handler, now=100.0)
        self.assertEqual(res1, 20)
        self.assertEqual(call_count[0], 1)

        # Retry identical event
        res2 = consumer.process("evt-1", {"val": 10}, handler, now=110.0)
        self.assertEqual(res2, 20)
        # Handler must NOT be called again
        self.assertEqual(call_count[0], 1)

    def test_conflicting_payload_for_same_id_rejected(self):
        consumer = IdempotentConsumer(window_seconds=60.0)
        consumer.process("evt-1", {"val": 10}, lambda p: "ok", now=100.0)

        # Reusing evt-1 with different payload must raise ConflictingPayloadError
        with self.assertRaises(ConflictingPayloadError):
            consumer.process("evt-1", {"val": 999}, lambda p: "ok", now=105.0)
