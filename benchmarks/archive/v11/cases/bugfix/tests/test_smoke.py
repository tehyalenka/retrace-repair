import unittest
from bookings import BookingService

class Smoke(unittest.TestCase):
    def test_book(self):
        service = BookingService({'show': 3})
        self.assertEqual(service.book('show', 'a', 1), 1)
