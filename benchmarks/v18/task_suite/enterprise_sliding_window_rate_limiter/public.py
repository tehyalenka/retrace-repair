import unittest
from sliding_limiter import SlidingWindowLogLimiter

class Public(unittest.TestCase):
    def test_requests_within_limit(self):
        limiter = SlidingWindowLogLimiter(max_requests=3, window_seconds=60.0)
        self.assertTrue(limiter.allow("user-1", now=10.0)[0])
        self.assertTrue(limiter.allow("user-1", now=20.0)[0])
        self.assertTrue(limiter.allow("user-1", now=30.0)[0])
        self.assertFalse(limiter.allow("user-1", now=40.0)[0])

    def test_sliding_window_boundary_burst_prevented(self):
        # 3 requests allowed per 60.0-second sliding window
        limiter = SlidingWindowLogLimiter(max_requests=3, window_seconds=60.0)

        # 3 requests at end of a fixed 60s boundary (t=58.0, 59.0, 59.5)
        self.assertTrue(limiter.allow("user-1", now=58.0)[0])
        self.assertTrue(limiter.allow("user-1", now=59.0)[0])
        self.assertTrue(limiter.allow("user-1", now=59.5)[0])

        # At t=60.5 (just crossed fixed window boundary 60s),
        # but in sliding window [0.5, 60.5], 3 requests were already made!
        # A true sliding limiter MUST reject this request:
        allowed, count = limiter.allow("user-1", now=60.5)
        self.assertFalse(allowed, "Allowed burst exceeding sliding rate across boundary!")
