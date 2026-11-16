import unittest
from orders import checkout
class Verify(unittest.TestCase):
    def test_heldout(self):
        self.assertAlmostEqual(checkout(100,0.15),115)
