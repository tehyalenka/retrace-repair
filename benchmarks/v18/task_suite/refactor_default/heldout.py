import unittest
from collector import collect
class Verify(unittest.TestCase):
    def test_heldout(self):
        collect(1); self.assertEqual(collect(2),[2])
