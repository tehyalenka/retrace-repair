import unittest
from connection_pool import ConnectionPool, ConnectionPoolExhaustedError

class Public(unittest.TestCase):
    def test_acquire_and_release(self):
        pool = ConnectionPool(max_size=2)
        c1 = pool.acquire()
        self.assertEqual(c1.conn_id, 1)
        pool.release(c1)

        c1_reused = pool.acquire()
        self.assertEqual(c1_reused.conn_id, 1)

    def test_pool_exhaustion_raises_error(self):
        pool = ConnectionPool(max_size=2, timeout=0.1)
        c1 = pool.acquire()
        c2 = pool.acquire()

        # Both connections checked out. 3rd attempt must raise ConnectionPoolExhaustedError
        with self.assertRaises(ConnectionPoolExhaustedError):
            pool.acquire(timeout=0.1)

        pool.release(c1)
        pool.release(c2)
