import unittest
from mapping import clone
class Verify(unittest.TestCase):
    def test_public(self):
        original={"a":1}; clone(original)["b"]=2; self.assertEqual(original,{"a":1})
