import unittest
from inventory import after_sale
class Verify(unittest.TestCase):
    def test_heldout(self):
        self.assertEqual(after_sale(9,3),6)
