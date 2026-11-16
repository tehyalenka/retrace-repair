import unittest
from sorting import sorted_copy
class Verify(unittest.TestCase):
    def test_heldout(self):
        items=[3,1,2]; self.assertEqual(sorted_copy(items),[1,2,3]); self.assertEqual(items,[3,1,2])
