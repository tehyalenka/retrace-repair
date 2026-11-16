import unittest
from match import matches
class Verify(unittest.TestCase):
    def test_public(self):
        self.assertTrue(matches("ABC","abc"))
