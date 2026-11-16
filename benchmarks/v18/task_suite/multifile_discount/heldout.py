import unittest
from api import total
class Verify(unittest.TestCase):
    def test_heldout(self):
        self.assertEqual(total(200,25),150)
