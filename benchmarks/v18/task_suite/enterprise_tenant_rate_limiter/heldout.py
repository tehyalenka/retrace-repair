import unittest
from tenant_limiter import HierarchicalTenantRateLimiter

class Heldout(unittest.TestCase):
    def test_global_limit_exhaustion_blocks_all_tenants(self):
        limiter = HierarchicalTenantRateLimiter(global_limit=2.0)
        # 2 requests consume global capacity
        limiter.allow_request("t1", "enterprise", now=100.0)
        limiter.allow_request("t2", "enterprise", now=100.0)

        # 3rd request blocked by global limit
        allowed, retry_after = limiter.allow_request("t3", "enterprise", now=100.0)
        self.assertFalse(allowed)
        self.assertGreater(retry_after, 0.0)

    def test_bucket_capacity_clamped_after_long_idle(self):
        limiter = HierarchicalTenantRateLimiter(global_limit=50.0)
        # Advance time by 1000 seconds
        limiter.allow_request("t1", "free", now=1000.0)
        # Should only have 5 tokens capacity, not 1000*5 = 5000 tokens!
        for _ in range(4):
            allowed, _ = limiter.allow_request("t1", "free", now=1000.0)
            self.assertTrue(allowed)

        # 6th request must fail
        allowed6, _ = limiter.allow_request("t1", "free", now=1000.0)
        self.assertFalse(allowed6)

    def test_invalid_parameters_raise_value_error(self):
        limiter = HierarchicalTenantRateLimiter()
        with self.assertRaises(ValueError):
            limiter.allow_request("", "free")
        with self.assertRaises(ValueError):
            limiter.allow_request("t1", "invalid_tier")
        with self.assertRaises(ValueError):
            HierarchicalTenantRateLimiter(global_limit=-10.0)
