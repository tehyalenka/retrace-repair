import unittest
from calc import double

class HeldoutCheck(unittest.TestCase):
    def test_negative(self):
        self.assertEqual(double(-4), -8)

    def test_float(self):
        self.assertEqual(double(1.5), 3.0)
