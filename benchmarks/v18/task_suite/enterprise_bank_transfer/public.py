import unittest
from storage import connect
from transfers import BankTransferService

class Public(unittest.TestCase):
    def test_transfer_success(self):
        d = connect()
        s = BankTransferService(d)
        s.seed('A', 1000)
        s.seed('B', 500)
        self.assertIs(s.transfer('t1', 'A', 'B', 200), True)
        self.assertEqual(s.balance('A'), 800)
        self.assertEqual(s.balance('B'), 700)
        self.assertEqual(s.transfer_count(), 1)

    def test_idempotent_duplicate_transfer(self):
        d = connect()
        s = BankTransferService(d)
        s.seed('A', 1000)
        s.seed('B', 500)
        self.assertIs(s.transfer('t1', 'A', 'B', 200), True)
        self.assertIs(s.transfer('t1', 'A', 'B', 200), True)
        self.assertEqual(s.balance('A'), 800)
        self.assertEqual(s.balance('B'), 700)
        self.assertEqual(s.transfer_count(), 1)

    def test_self_transfer_rejected(self):
        d = connect()
        s = BankTransferService(d)
        s.seed('A', 1000)
        with self.assertRaises(ValueError):
            s.transfer('t1', 'A', 'A', 100)
        self.assertEqual(s.balance('A'), 1000)

    def test_insufficient_funds_returns_false(self):
        d = connect()
        s = BankTransferService(d)
        s.seed('A', 100)
        s.seed('B', 50)
        self.assertIs(s.transfer('t1', 'A', 'B', 500), False)
        self.assertEqual(s.balance('A'), 100)
        self.assertEqual(s.balance('B'), 50)
