import unittest
from counts import frequencies
class Verify(unittest.TestCase):
    def test_heldout(self):
        self.assertEqual(frequencies(["a","b","a"]),{"a":2,"b":1})
