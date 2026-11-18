import unittest
from sliding_limiter import SlidingWindowLogLimiter

class Heldout(unittest.TestCase):
    def test_log_pruning_and_recovery_after_window(self):
        limiter = SlidingWindowLogLimiter(max_requests=2, window_seconds=10.0)
        limiter.allow("k1", now=1.0)
        limiter.allow("k1", now=2.0)
        self.assertFalse(limiter.allow("k1", now=3.0)[0])

        # At t=11.5, t=1.0 has expired (cutoff = 1.5). 1 active request remains.
        # So 1 new request is allowed.
        self.assertTrue(limiter.allow("k1", now=11.5)[0])

        # At t=12.5, t=2.0 has expired. Another request is allowed.
        self.assertTrue(limiter.allow("k1", now=12.5)[0])

    def test_key_isolation(self):
        limiter = SlidingWindowLogLimiter(max_requests=1, window_seconds=10.0)
        self.assertTrue(limiter.allow("k1", now=1.0)[0])
        self.assertFalse(limiter.allow("k1", now=2.0)[0])

        # k2 is unaffected
        self.assertTrue(limiter.allow("k2", now=2.0)[0])

    def test_invalid_parameters_raise_value_error(self):
        with self.assertRaises(ValueError):
            SlidingWindowLogLimiter(max_requests=0)
        with self.assertRaises(ValueError):
            SlidingWindowLogLimiter(window_seconds=-1.0)

        limiter = SlidingWindowLogLimiter()
        with self.assertRaises(ValueError):
            limiter.allow("")
