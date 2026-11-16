import unittest
from mapping import clone
class Verify(unittest.TestCase):
    def test_heldout(self):
        original={"a":1}; result=clone(original); result["b"]=2; self.assertEqual(original,{"a":1})
