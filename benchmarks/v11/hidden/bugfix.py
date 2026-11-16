import unittest
from bookings import BookingService

class BookingVerification(unittest.TestCase):
    def test_cancel_once(self):
        s = BookingService({'a': 5})
        booking = s.book('a', 'bob', 2)
        self.assertEqual(s.seats.remaining['a'], 3)
        self.assertTrue(s.cancel(booking))
        self.assertEqual(s.seats.remaining['a'], 5)
        self.assertEqual(s.ledger.refunds[booking], 50)
        self.assertFalse(s.cancel(booking))
        self.assertEqual(s.seats.remaining['a'], 5)
        self.assertEqual(s.ledger.refunds[booking], 50)
    def test_unknown(self):
        s = BookingService({'a': 1})
        self.assertFalse(s.cancel(123))
    def test_insufficient(self):
        s = BookingService({'a': 1})
        with self.assertRaises(ValueError): s.book('a', 'bob', 2)
        self.assertEqual(s.seats.remaining['a'], 1)
        self.assertEqual(s.ledger.charges, {})
    def test_invalid(self):
        s = BookingService({'a': 3})
        for count in (0, -1, 1.5, True):
            with self.subTest(count=count):
                with self.assertRaises(ValueError): s.book('a', 'bob', count)
        self.assertEqual(s.seats.remaining['a'], 3)
