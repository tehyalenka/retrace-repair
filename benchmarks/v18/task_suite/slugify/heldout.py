import unittest
from slug import slugify
class Verify(unittest.TestCase):
    def test_heldout(self):
        self.assertEqual(slugify("Hello   World"),"hello-world")
