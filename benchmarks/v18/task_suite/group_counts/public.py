import unittest
from counts import frequencies
class Verify(unittest.TestCase):
    def test_public(self):
        self.assertEqual(frequencies(["a","a"]),{"a":2})
