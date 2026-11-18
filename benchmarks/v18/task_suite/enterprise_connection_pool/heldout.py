import unittest
import threading
from connection_pool import ConnectionPool, ConnectionPoolExhaustedError

class Heldout(unittest.TestCase):
    def test_dead_connection_evicted_and_replaced(self):
        pool = ConnectionPool(max_size=1)
        c1 = pool.acquire()
        self.assertEqual(c1.conn_id, 1)

        # Connection drops/dies
        c1.close()
        pool.release(c1)

        # Re-acquire: pool detects dead connection, drops it, creates replacement c2
        c2 = pool.acquire()
        self.assertTrue(c2.is_alive())
        self.assertEqual(c2.conn_id, 2)
        pool.release(c2)

    def test_context_manager(self):
        pool = ConnectionPool(max_size=1)
        with pool.get_connection() as conn:
            self.assertTrue(conn.is_alive())

        # Released automatically by context manager: can acquire again
        c = pool.acquire()
        self.assertIsNotNone(c)
        pool.release(c)

    def test_invalid_parameters_raise_value_error(self):
        with self.assertRaises(ValueError):
            ConnectionPool(max_size=0)
        with self.assertRaises(ValueError):
            ConnectionPool(timeout=-1.0)
        pool = ConnectionPool()
        with self.assertRaises(ValueError):
            pool.release("not a connection")
