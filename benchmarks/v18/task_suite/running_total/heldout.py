import unittest
from series import running_total
class Verify(unittest.TestCase):
    def test_heldout(self):
        self.assertEqual(running_total([1,2,3]),[1,3,6])
