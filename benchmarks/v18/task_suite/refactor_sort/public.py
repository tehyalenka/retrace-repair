import unittest
from sorting import sorted_copy
class Verify(unittest.TestCase):
    def test_public(self):
        items=[2,1]; sorted_copy(items); self.assertEqual(items,[2,1])
