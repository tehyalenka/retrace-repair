import unittest
import threading
import time
from bulkhead import TenantBulkhead, BulkheadFullError

class Heldout(unittest.TestCase):
    def test_queue_overflow_rejection(self):
        bh = TenantBulkhead(max_concurrent=1, max_queue_size=1)
        holding = threading.Event()
        release = threading.Event()

        def job():
            holding.set()
            release.wait(timeout=2.0)

        # 1 active
        t1 = threading.Thread(target=lambda: bh.execute("t1", job), daemon=True)
        t1.start()
        if not holding.wait(timeout=1.0):
            self.fail("Timed out waiting for worker")

        # 1 queued
        t2_started = threading.Event()
        t2_done = threading.Event()
        def queued_job():
            t2_started.set()
            bh.execute("t1", lambda: "ok")
            t2_done.set()

        t2 = threading.Thread(target=queued_job, daemon=True)
        t2.start()
        time.sleep(0.05)

        # 3rd request overflows queue (capacity = 1 active + 1 queue = 2)
        with self.assertRaises(BulkheadFullError):
            bh.execute("t1", lambda: 1)

        release.set()
        t1.join(timeout=1.0)
        t2.join(timeout=1.0)
        self.assertTrue(t2_done.is_set())

    def test_exception_in_worker_frees_capacity(self):
        bh = TenantBulkhead(max_concurrent=1, max_queue_size=0)
        def failing():
            raise RuntimeError("inner error")

        with self.assertRaises(RuntimeError):
            bh.execute("t1", failing)

        # Capacity freed: next request succeeds
        res = bh.execute("t1", lambda: 99)
        self.assertEqual(res, 99)

    def test_invalid_parameters_raise_value_error(self):
        with self.assertRaises(ValueError):
            TenantBulkhead(max_concurrent=0)
        with self.assertRaises(ValueError):
            TenantBulkhead(max_queue_size=-1)

        bh = TenantBulkhead()
        with self.assertRaises(ValueError):
            bh.execute("", lambda: 1)
        with self.assertRaises(ValueError):
            bh.execute("t", "not callable")
