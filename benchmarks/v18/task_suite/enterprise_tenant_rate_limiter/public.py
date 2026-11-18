import unittest
from tenant_limiter import HierarchicalTenantRateLimiter

class Public(unittest.TestCase):
    def test_tenant_under_tier_limit_allowed(self):
        limiter = HierarchicalTenantRateLimiter()
        allowed, retry_after = limiter.allow_request("tenant-1", "free", now=100.0)
        self.assertTrue(allowed)
        self.assertEqual(retry_after, 0.0)

    def test_tenant_exceeding_tier_quota_rejected(self):
        limiter = HierarchicalTenantRateLimiter(global_limit=100.0)
        # Free tier has 5 tokens
        for _ in range(5):
            allowed, _ = limiter.allow_request("free-tenant", "free", now=100.0)
            self.assertTrue(allowed)

        # 6th request at the same timestamp must be rejected by tenant tier limit
        allowed6, retry_after = limiter.allow_request("free-tenant", "free", now=100.0)
        self.assertFalse(allowed6)
        self.assertGreater(retry_after, 0.0)
