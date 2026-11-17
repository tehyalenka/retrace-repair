import unittest
from storage import connect
from transfers import BankTransferService

class Heldout(unittest.TestCase):
    def test_conflicting_payload_duplicate_rejected(self):
        d = connect()
        s = BankTransferService(d)
        s.seed('A', 1000)
        s.seed('B', 500)
        s.seed('C', 200)
        self.assertIs(s.transfer('t1', 'A', 'B', 200), True)
        with self.assertRaises(ValueError):
            s.transfer('t1', 'A', 'C', 200)
        with self.assertRaises(ValueError):
            s.transfer('t1', 'A', 'B', 300)
        self.assertEqual(s.balance('A'), 800)
        self.assertEqual(s.balance('B'), 700)
        self.assertEqual(s.balance('C'), 200)

    def test_invalid_amount_types_rejected(self):
        d = connect()
        s = BankTransferService(d)
        s.seed('A', 1000)
        s.seed('B', 500)
        for bad in [0, -50, True, False, 100.5, '200', None]:
            with self.assertRaises(ValueError):
                s.transfer('t-bad', 'A', 'B', bad)
        self.assertEqual(s.balance('A'), 1000)
        self.assertEqual(s.balance('B'), 500)

    def test_rollback_on_destination_write_error(self):
        d = connect()
        s = BankTransferService(d)
        s.seed('A', 1000)
        s.seed('B', 500)
        d.execute('CREATE TRIGGER fail_dest BEFORE UPDATE ON accounts WHEN NEW.id="B" BEGIN SELECT RAISE(ABORT, "account B locked"); END;')
        d.commit()
        with self.assertRaises(Exception):
            s.transfer('t-err', 'A', 'B', 100)
        self.assertEqual(s.balance('A'), 1000)
        self.assertEqual(s.balance('B'), 500)
        self.assertEqual(s.transfer_count(), 0)

    def test_total_balance_invariant(self):
        d = connect()
        s = BankTransferService(d)
        s.seed('A', 5000)
        s.seed('B', 5000)
        total_initial = s.balance('A') + s.balance('B')
        for i in range(10):
            s.transfer(f'tx-{i}', 'A', 'B', 200)
        self.assertEqual(s.balance('A') + s.balance('B'), total_initial)
        self.assertEqual(s.balance('A'), 3000)
        self.assertEqual(s.balance('B'), 7000)
