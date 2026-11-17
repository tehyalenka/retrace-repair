import unittest
from storage import connect
from orders import OrderService


class Public(unittest.TestCase):
    def test_idempotent_retry(self):
        d = connect()
        s = OrderService(d)
        s.seed('A', 5)
        self.assertTrue(s.place('req-1', 'A', 2))
        self.assertTrue(s.place('req-1', 'A', 2))
        self.assertEqual(s.available('A'), 3)
        self.assertEqual(s.event_count(), 1)

    def test_zero_quantity_rejected_without_side_effects(self):
        d = connect()
        s = OrderService(d)
        s.seed('A', 5)
        with self.assertRaises(ValueError):
            s.place('bad-qty', 'A', 0)
        self.assertEqual(s.available('A'), 5)
        self.assertEqual(s.event_count(), 0)

    def test_conflicting_idempotency_key_rejected(self):
        d = connect()
        s = OrderService(d)
        s.seed('A', 5)
        self.assertTrue(s.place('req-1', 'A', 2))
        with self.assertRaises(ValueError):
            s.place('req-1', 'A', 3)
        self.assertEqual(s.available('A'), 3)
        self.assertEqual(s.event_count(), 1)
