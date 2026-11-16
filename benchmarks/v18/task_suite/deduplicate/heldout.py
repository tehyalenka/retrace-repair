import unittest
from utils import unique
class Verify(unittest.TestCase):
    def test_heldout(self):
        self.assertEqual(unique([3,1,3,2,1]),[3,1,2])
