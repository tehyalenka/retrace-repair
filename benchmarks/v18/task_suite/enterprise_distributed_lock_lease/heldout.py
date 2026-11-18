import unittest
from lock import DistributedLockManager

class Heldout(unittest.TestCase):
    def test_stale_owner_cannot_release_after_expiry(self):
        lm = DistributedLockManager()
        lm.acquire("res1", "worker-A", ttl_seconds=5.0, now=100.0)

        # Lease expires, worker B acquires
        lm.acquire("res1", "worker-B", ttl_seconds=5.0, now=106.0)

        # Worker A tries to release, must fail
        self.assertFalse(lm.release("res1", "worker-A", now=107.0))

        # Worker B's lock remains intact
        acq, _ = lm.acquire("res1", "worker-C", ttl_seconds=5.0, now=108.0)
        self.assertFalse(acq)

    def test_legitimate_release_allows_immediate_reacquire(self):
        lm = DistributedLockManager()
        lm.acquire("res1", "worker-A", ttl_seconds=10.0, now=100.0)
        self.assertTrue(lm.release("res1", "worker-A", now=101.0))

        # Worker B can immediately acquire
        acq, token = lm.acquire("res1", "worker-B", ttl_seconds=10.0, now=102.0)
        self.assertTrue(acq)

    def test_monotonic_tokens_across_multiple_cycles(self):
        lm = DistributedLockManager()
        tokens = []
        for i in range(5):
            acq, tok = lm.acquire("res1", f"w-{i}", ttl_seconds=1.0, now=100.0 + i * 2.0)
            self.assertTrue(acq)
            tokens.append(tok)
        self.assertEqual(tokens, sorted(tokens))
        self.assertEqual(len(set(tokens)), 5)

    def test_invalid_parameters_raise_value_error(self):
        lm = DistributedLockManager()
        with self.assertRaises(ValueError):
            lm.acquire("", "w1", 5.0)
        with self.assertRaises(ValueError):
            lm.acquire("res", "", 5.0)
        with self.assertRaises(ValueError):
            lm.acquire("res", "w1", -1.0)
