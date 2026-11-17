import unittest
from storage import connect
from limiter import TokenBucketRateLimiter

class Heldout(unittest.TestCase):
    def test_clock_drift_protection(self):
        lim = TokenBucketRateLimiter(connect())
        lim.configure("tenant-1", capacity=10, refill_rate=2, now=100.0)
        lim.consume("tenant-1", tokens=5, now=100.0)

        # Backward time (clock jump backwards) should not corrupt tokens
        allowed, remaining, _ = lim.consume("tenant-1", tokens=1, now=90.0)
        self.assertIs(allowed, True)
        self.assertEqual(remaining, 4.0)

    def test_capacity_is_upper_bound(self):
        lim = TokenBucketRateLimiter(connect())
        lim.configure("tenant-1", capacity=10, refill_rate=5, now=100.0)
        # Advance 100 seconds: capacity remains 10
        allowed, remaining, _ = lim.consume("tenant-1", tokens=10, now=200.0)
        self.assertIs(allowed, True)
        self.assertEqual(remaining, 0.0)

    def test_invalid_tokens_rejected(self):
        lim = TokenBucketRateLimiter(connect())
        lim.configure("tenant-1", capacity=10, refill_rate=1, now=100.0)
        for bad in [0, -1, True, False, 1.5, "1"]:
            with self.assertRaises(ValueError):
                lim.consume("tenant-1", tokens=bad, now=100.0)
