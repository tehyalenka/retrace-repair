import unittest
from storage import connect
from limiter import TokenBucketRateLimiter

class Public(unittest.TestCase):
    def test_consume_and_refill(self):
        lim = TokenBucketRateLimiter(connect())
        lim.configure("tenant-1", capacity=10, refill_rate=2, now=100.0)

        # Consume 8 of 10
        allowed, remaining, wait = lim.consume("tenant-1", tokens=8, now=100.0)
        self.assertIs(allowed, True)
        self.assertEqual(remaining, 2.0)
        self.assertEqual(wait, 0.0)

        # Trying to consume 5 immediately fails
        allowed, remaining, wait = lim.consume("tenant-1", tokens=5, now=100.0)
        self.assertIs(allowed, False)
        self.assertEqual(remaining, 2.0)
        self.assertGreater(wait, 0.0)

        # After 2 seconds, 4 tokens refilled (2.0 + 4 = 6.0)
        allowed, remaining, wait = lim.consume("tenant-1", tokens=5, now=102.0)
        self.assertIs(allowed, True)
        self.assertEqual(remaining, 1.0)
