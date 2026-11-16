import unittest
from text import normalize
class Verify(unittest.TestCase):
    def test_public(self):
        self.assertEqual(normalize("a  b"),"a b")
