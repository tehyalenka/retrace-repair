import unittest
from stats import mean
class Verify(unittest.TestCase):
    def test_heldout(self):
        self.assertEqual(mean([]),0)
