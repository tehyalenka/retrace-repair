import unittest
from burst_bucket import BurstTokenBucket

class Heldout(unittest.TestCase):
    def test_burst_capacity_ceiling_clamp(self):
        bucket = BurstTokenBucket(sustained_rate=10.0, burst_capacity=25.0)
        # Advance 100 seconds
        bucket.consume(1.0, now=100.0)
        # Tokens should not exceed 25.0 - 1.0 = 24.0
        allowed, rem = bucket.consume(24.0, now=100.0)
        self.assertTrue(allowed)
        self.assertAlmostEqual(rem, 0.0)

    def test_consumption_exceeding_capacity_rejected(self):
        bucket = BurstTokenBucket(sustained_rate=10.0, burst_capacity=20.0)
        allowed, rem = bucket.consume(50.0, now=100.0)
        self.assertFalse(allowed)

    def test_invalid_parameters_raise_value_error(self):
        with self.assertRaises(ValueError):
            BurstTokenBucket(sustained_rate=0)
        with self.assertRaises(ValueError):
            BurstTokenBucket(burst_capacity=-5)
        bucket = BurstTokenBucket()
        with self.assertRaises(ValueError):
            bucket.consume(0)
        with self.assertRaises(ValueError):
            bucket.consume(-2)
