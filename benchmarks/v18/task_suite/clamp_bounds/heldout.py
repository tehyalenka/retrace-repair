import unittest
from calc import clamp
class Verify(unittest.TestCase):
    def test_heldout(self):
        self.assertEqual(clamp(-4,0,5),0)
