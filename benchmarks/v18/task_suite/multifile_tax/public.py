import unittest
from orders import checkout
class Verify(unittest.TestCase):
    def test_public(self):
        self.assertAlmostEqual(checkout(100,0.1),110)
