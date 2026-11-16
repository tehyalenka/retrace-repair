import unittest
from catalog import checkout

class IndependentCheckoutTests(unittest.TestCase):
    def test_discount_fraction(self):
        self.assertEqual(checkout([(100, 2)], 0.10, 0), 180)
    def test_tax_fraction(self):
        self.assertEqual(checkout([(100, 1)], 0, 0.05), 105)
    def test_combined(self):
        self.assertEqual(checkout([(100, 2)], 0.10, 0.05), 189)
    def test_invalid_discount(self):
        with self.assertRaises(ValueError): checkout([(10, 1)], 1.1, 0)
    def test_invalid_tax(self):
        with self.assertRaises(ValueError): checkout([(10, 1)], 0, -0.1)
    def test_negative_quantity(self):
        with self.assertRaises(ValueError): checkout([(10, -1)], 0, 0)
