import unittest

from accounts import Account
from transfers import transfer


class TransferTests(unittest.TestCase):
    def test_successful_transfer(self):
        a = Account("A", 10000)
        b = Account("B", 2000)

        transfer(a, b, 3000)

        self.assertEqual(a.balance, 7000)
        self.assertEqual(b.balance, 5000)

    def test_insufficient_funds(self):
        a = Account("A", 1000)
        b = Account("B", 2000)

        with self.assertRaises(ValueError):
            transfer(a, b, 3000)

        self.assertEqual((a.balance, b.balance), (1000, 2000))

    def test_invalid_amount(self):
        a = Account("A", 1000)
        b = Account("B", 2000)

        with self.assertRaises(ValueError):
            transfer(a, b, 0)

    def test_total_balance_preserved(self):
        a = Account("A", 8000)
        b = Account("B", 4000)

        transfer(a, b, 2500)

        self.assertEqual(a.balance + b.balance, 12000)


if __name__ == "__main__":
    unittest.main()
