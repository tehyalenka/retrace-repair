import unittest
from api import total
class Verify(unittest.TestCase):
    def test_public(self):
        self.assertEqual(total(100,20),80)
