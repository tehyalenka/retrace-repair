import unittest

from accounts import Account
from transfers import transfer


class IndependentTransferTests(unittest.TestCase):

    def test_negative_amount(self):
        a, b = Account("A", 1000), Account("B", 500)
        with self.assertRaises(ValueError):
            transfer(a, b, -100)
        self.assertEqual((a.balance, b.balance), (1000, 500))

    def test_boolean_amount(self):
        a, b = Account("A", 1000), Account("B", 500)
        with self.assertRaises(ValueError):
            transfer(a, b, True)

    def test_float_amount(self):
        a, b = Account("A", 1000), Account("B", 500)
        with self.assertRaises(ValueError):
            transfer(a, b, 100.5)

    def test_same_account(self):
        a = Account("A", 1000)
        with self.assertRaises(ValueError):
            transfer(a, a, 100)
        self.assertEqual(a.balance, 1000)

    def test_full_balance_transfer(self):
        a, b = Account("A", 1000), Account("B", 500)
        transfer(a, b, 1000)
        self.assertEqual((a.balance, b.balance), (0, 1500))


if __name__ == "__main__":
    unittest.main()
