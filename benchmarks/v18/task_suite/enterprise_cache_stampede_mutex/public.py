import unittest
import threading
import time
from stampede_cache import StampedeCache

class Public(unittest.TestCase):
    def test_single_call_caches_value(self):
        cache = StampedeCache()
        calls = [0]
        def loader():
            calls[0] += 1
            return "data"

        val1 = cache.get_or_compute("k1", loader, ttl_seconds=10.0, now=100.0)
        self.assertEqual(val1, "data")
        self.assertEqual(calls[0], 1)

        val2 = cache.get_or_compute("k1", loader, ttl_seconds=10.0, now=105.0)
        self.assertEqual(val2, "data")
        self.assertEqual(calls[0], 1)

    def test_single_flight_coalescing_under_concurrency(self):
        cache = StampedeCache()
        loader_calls = [0]
        start_event = threading.Event()

        def slow_loader():
            loader_calls[0] += 1
            time.sleep(0.05)
            return "heavy-computation-result"

        results = []
        threads = []

        def worker():
            start_event.wait()
            res = cache.get_or_compute("expensive-key", slow_loader, ttl_seconds=10.0, now=100.0)
            results.append(res)

        for _ in range(5):
            t = threading.Thread(target=worker, daemon=True)
            threads.append(t)
            t.start()

        start_event.set()
        for t in threads:
            t.join(timeout=1.0)

        self.assertEqual(len(results), 5)
        for r in results:
            self.assertEqual(r, "heavy-computation-result")

        # Single flight guarantee: exactly 1 call to slow_loader despite 5 simultaneous requests!
        self.assertEqual(loader_calls[0], 1, "Cache stampede occurred! Multiple loaders executed!")
