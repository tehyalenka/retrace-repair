import unittest
from bank import Bank

class Smoke(unittest.TestCase):
    def test_balance(self):
        self.assertEqual(Bank({'a': 5}).balance('a'), 5)
