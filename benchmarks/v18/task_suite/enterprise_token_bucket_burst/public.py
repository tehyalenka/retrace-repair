import unittest
from burst_bucket import BurstTokenBucket

class Public(unittest.TestCase):
    def test_burst_up_to_capacity(self):
        bucket = BurstTokenBucket(sustained_rate=5.0, burst_capacity=10.0)
        # Consume full burst capacity
        self.assertTrue(bucket.consume(10.0, now=100.0)[0])
        # Next request fails
        self.assertFalse(bucket.consume(1.0, now=100.0)[0])

    def test_fractional_subsecond_refill(self):
        # 10 tokens/sec sustained rate
        bucket = BurstTokenBucket(sustained_rate=10.0, burst_capacity=20.0)
        bucket.consume(20.0, now=100.0) # Drain bucket

        # Advance 0.5s (500ms): should refill 0.5 * 10 = 5 tokens!
        allowed, rem = bucket.consume(4.0, now=100.5)
        self.assertTrue(allowed, "Fractional subsecond refill failed!")
        self.assertAlmostEqual(rem, 1.0)
