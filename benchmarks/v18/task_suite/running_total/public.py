import unittest
from series import running_total
class Verify(unittest.TestCase):
    def test_public(self):
        self.assertEqual(running_total([1,2]),[1,3])
