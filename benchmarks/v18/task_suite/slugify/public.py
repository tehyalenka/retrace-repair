import unittest
from slug import slugify
class Verify(unittest.TestCase):
    def test_public(self):
        self.assertEqual(slugify("Hello World"),"hello-world")
