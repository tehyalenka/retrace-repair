import unittest
from text import normalize
class Verify(unittest.TestCase):
    def test_heldout(self):
        self.assertEqual(normalize(" a  b\tc "),"a b c")
