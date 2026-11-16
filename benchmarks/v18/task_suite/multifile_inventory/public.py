import unittest
from inventory import after_sale
class Verify(unittest.TestCase):
    def test_public(self):
        self.assertEqual(after_sale(5,2),3)
