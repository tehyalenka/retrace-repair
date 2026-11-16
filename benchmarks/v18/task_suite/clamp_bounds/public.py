import unittest
from calc import clamp
class Verify(unittest.TestCase):
    def test_public(self):
        self.assertEqual(clamp(-1,0,5),0)
