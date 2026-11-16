import unittest
from match import matches
class Verify(unittest.TestCase):
    def test_heldout(self):
        self.assertTrue(matches("ABC","abc")); self.assertFalse(matches("ab","abc"))
