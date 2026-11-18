import unittest
from adaptive_limiter import AdaptiveConcurrencyLimiter

class Public(unittest.TestCase):
    def test_additive_increase_under_healthy_rtt(self):
        limiter = AdaptiveConcurrencyLimiter(initial_limit=10, min_limit=5, max_limit=30)
        limiter.acquire()
        limiter.release(measured_rtt=10.0) # Baseline min_rtt = 10.0

        limiter.acquire()
        limiter.release(measured_rtt=10.5) # Healthy RTT
        self.assertGreater(limiter.limit, 10.0)

    def test_backoff_throttle_under_latency_spike(self):
        limiter = AdaptiveConcurrencyLimiter(initial_limit=20, min_limit=5, max_limit=40)
        limiter.acquire()
        limiter.release(measured_rtt=10.0) # Baseline min_rtt = 10.0

        # Latency spikes to 50.0 (5x baseline) due to downstream bottleneck
        limiter.acquire()
        limiter.release(measured_rtt=50.0)

        # Concurrency limit MUST throttle downwards
        self.assertLess(limiter.limit, 20.0, "Limiter failed to throttle down during latency spike!")
