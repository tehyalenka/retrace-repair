import unittest
import threading
import time
from stampede_cache import StampedeCache

class Heldout(unittest.TestCase):
    def test_cache_expiration_triggers_fresh_recomputation(self):
        cache = StampedeCache()
        count = [0]
        def loader():
            count[0] += 1
            return count[0]

        val1 = cache.get_or_compute("k", loader, ttl_seconds=5.0, now=100.0)
        self.assertEqual(val1, 1)

        # Still valid at 104.0
        val2 = cache.get_or_compute("k", loader, ttl_seconds=5.0, now=104.0)
        self.assertEqual(val2, 1)

        # Expired at 106.0 -> calls loader again
        val3 = cache.get_or_compute("k", loader, ttl_seconds=5.0, now=106.0)
        self.assertEqual(val3, 2)
        self.assertEqual(count[0], 2)

    def test_loader_exception_propagates_without_stuck_locks(self):
        cache = StampedeCache()
        def failing_loader():
            raise RuntimeError("backend failed")

        with self.assertRaises(RuntimeError):
            cache.get_or_compute("err-key", failing_loader, ttl_seconds=10.0)

        # Subsequent call can retry and compute successfully
        val = cache.get_or_compute("err-key", lambda: "recovered", ttl_seconds=10.0)
        self.assertEqual(val, "recovered")

    def test_invalid_parameters_raise_value_error(self):
        cache = StampedeCache()
        with self.assertRaises(ValueError):
            cache.get_or_compute("", lambda: 1, 10.0)
        with self.assertRaises(ValueError):
            cache.get_or_compute("k", "not callable", 10.0)
        with self.assertRaises(ValueError):
            cache.get_or_compute("k", lambda: 1, -1.0)
