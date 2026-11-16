import unittest
from collector import collect
class Verify(unittest.TestCase):
    def test_public(self):
        collect(1); self.assertEqual(collect(2),[2])
