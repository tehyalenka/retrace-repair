import unittest
from catalog import checkout

class CheckoutSmoke(unittest.TestCase):
    def test_no_discount_or_tax(self):
        self.assertEqual(checkout([(10, 2)], 0, 0), 20)
