import unittest
from calc import double

class PublicCheck(unittest.TestCase):
    def test_positive(self):
        self.assertEqual(double(3), 6)
