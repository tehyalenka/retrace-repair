import unittest
from diff import distance
class Verify(unittest.TestCase):
    def test_heldout(self):
        self.assertEqual(distance(2,4),2)
