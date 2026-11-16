import unittest
from stats import mean
class Verify(unittest.TestCase):
    def test_public(self):
        self.assertEqual(mean([]),0)
