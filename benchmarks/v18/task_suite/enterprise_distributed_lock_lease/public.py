import unittest
from lock import DistributedLockManager

class Public(unittest.TestCase):
    def test_acquire_and_renew(self):
        lm = DistributedLockManager()
        acquired, token = lm.acquire("res1", "worker-A", ttl_seconds=10.0, now=100.0)
        self.assertTrue(acquired)
        self.assertGreater(token, 0)

        # Renew before expiration succeeds
        renewed = lm.renew("res1", "worker-A", ttl_seconds=10.0, now=105.0)
        self.assertTrue(renewed)

    def test_expired_lease_cannot_renew_and_allows_reacquire(self):
        lm = DistributedLockManager()
        acquired1, token1 = lm.acquire("res1", "worker-A", ttl_seconds=5.0, now=100.0)
        self.assertTrue(acquired1)

        # Time advances past TTL (now=106.0)
        # Worker A cannot renew expired lease
        self.assertFalse(lm.renew("res1", "worker-A", ttl_seconds=5.0, now=106.0))

        # Worker B can acquire, getting a higher monotonic fencing token
        acquired2, token2 = lm.acquire("res1", "worker-B", ttl_seconds=5.0, now=106.0)
        self.assertTrue(acquired2)
        self.assertGreater(token2, token1)
