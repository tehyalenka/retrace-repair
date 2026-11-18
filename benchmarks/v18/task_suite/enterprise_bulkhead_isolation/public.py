import unittest
import threading
import time
from bulkhead import TenantBulkhead, BulkheadFullError

class Public(unittest.TestCase):
    def test_single_tenant_execution(self):
        bh = TenantBulkhead(max_concurrent=2, max_queue_size=2)
        res = bh.execute("tenant-A", lambda x: x * 2, 21)
        self.assertEqual(res, 42)

    def test_tenant_isolation_noisy_neighbor(self):
        # Tenant A saturates its pool and queue
        bh = TenantBulkhead(max_concurrent=1, max_queue_size=0)
        tenant_a_holding = threading.Event()
        tenant_a_finish = threading.Event()

        def slow_worker():
            tenant_a_holding.set()
            tenant_a_finish.wait(timeout=2.0)
            return "done"

        t = threading.Thread(target=lambda: bh.execute("tenant-A", slow_worker), daemon=True)
        t.start()
        if not tenant_a_holding.wait(timeout=1.0):
            self.fail("Timed out waiting for tenant-A worker")

        # Tenant A is saturated: another call for tenant A must raise BulkheadFullError
        with self.assertRaises(BulkheadFullError):
            bh.execute("tenant-A", lambda: 1)

        # BUT Tenant B is independent and MUST succeed immediately without error!
        res_b = bh.execute("tenant-B", lambda: "tenant-B-success")
        self.assertEqual(res_b, "tenant-B-success")

        tenant_a_finish.set()
        t.join(timeout=1.0)
