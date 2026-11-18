import unittest
from adaptive_limiter import AdaptiveConcurrencyLimiter

class Heldout(unittest.TestCase):
    def test_min_and_max_limit_clamping(self):
        limiter = AdaptiveConcurrencyLimiter(initial_limit=10, min_limit=5, max_limit=15)
        limiter.acquire()
        limiter.release(10.0)

        # Huge latency spike tries to drop limit below min_limit
        for _ in range(10):
            limiter.acquire()
            limiter.release(500.0)
        self.assertEqual(limiter.limit, 5.0)

        # Extended period of healthy traffic cannot exceed max_limit
        limiter.min_rtt = 1.0
        for _ in range(50):
            limiter.acquire()
            limiter.release(1.0)
        self.assertEqual(limiter.limit, 15.0)

    def test_acquire_saturation(self):
        limiter = AdaptiveConcurrencyLimiter(initial_limit=2, min_limit=2, max_limit=5)
        self.assertTrue(limiter.acquire())
        self.assertTrue(limiter.acquire())
        # Saturated: 3rd acquire fails
        self.assertFalse(limiter.acquire())

        limiter.release(10.0)
        self.assertTrue(limiter.acquire())

    def test_invalid_parameters_raise_value_error(self):
        with self.assertRaises(ValueError):
            AdaptiveConcurrencyLimiter(initial_limit=0)
        with self.assertRaises(ValueError):
            AdaptiveConcurrencyLimiter(min_limit=10, max_limit=5)
        limiter = AdaptiveConcurrencyLimiter()
        with self.assertRaises(ValueError):
            limiter.release(-5.0)
        with self.assertRaises(ValueError):
            limiter.release(0)
