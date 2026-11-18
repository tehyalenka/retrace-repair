import unittest
from event_sourcing import EventStore, BankAccountAggregate, OptimisticConcurrencyError

class Heldout(unittest.TestCase):
    def test_snapshot_and_tail_events(self):
        acc = BankAccountAggregate("acc-snap")
        acc.deposit(200)
        acc.deposit(100)
        acc.version = 2
        snapshot = acc.take_snapshot()

        # Rehydrate from snapshot + subsequent event
        acc2 = BankAccountAggregate("acc-snap")
        acc2.load_from_snapshot(snapshot)
        self.assertEqual(acc2.balance, 300)
        self.assertEqual(acc2.version, 2)

        tail_events = [{"type": "WITHDRAW", "amount": 50, "version": 3}]
        acc2.load_from_history(tail_events)
        self.assertEqual(acc2.balance, 250)
        self.assertEqual(acc2.version, 3)

    def test_overdraft_rejected(self):
        acc = BankAccountAggregate("acc-overdraft")
        acc.deposit(50)
        with self.assertRaises(ValueError):
            acc.withdraw(100)
        self.assertEqual(acc.balance, 50)

    def test_invalid_stream_id_or_version_types(self):
        store = EventStore()
        with self.assertRaises(ValueError):
            store.append_events("", [{"type": "A"}], 0)
        with self.assertRaises(ValueError):
            store.append_events("acc", [{"type": "A"}], -1)

    def test_zero_or_negative_amounts_rejected(self):
        acc = BankAccountAggregate("acc-bad")
        for bad in [0, -10, "50", None]:
            with self.assertRaises(ValueError):
                acc.deposit(bad)
            with self.assertRaises(ValueError):
                acc.withdraw(bad)
