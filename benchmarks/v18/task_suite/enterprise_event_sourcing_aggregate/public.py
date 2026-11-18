import unittest
from event_sourcing import EventStore, BankAccountAggregate, OptimisticConcurrencyError

class Public(unittest.TestCase):
    def test_deposit_and_replay(self):
        store = EventStore()
        acc = BankAccountAggregate("acc-1")
        acc.deposit(100)
        acc.deposit(50)

        # Append to store with expected_version=0
        new_ver = store.append_events("acc-1", acc.changes, expected_version=0)
        self.assertEqual(new_ver, 2)

        # Rehydrate in new aggregate
        acc2 = BankAccountAggregate("acc-1")
        acc2.load_from_history(store.get_events("acc-1"))
        self.assertEqual(acc2.balance, 150)
        self.assertEqual(acc2.version, 2)

    def test_optimistic_concurrency_conflict_detected(self):
        store = EventStore()
        # Initial events commit version 1
        store.append_events("acc-1", [{"type": "DEPOSIT", "amount": 100}], expected_version=0)

        # Concurrent attempt with stale expected_version 0 must fail
        with self.assertRaises(OptimisticConcurrencyError):
            store.append_events("acc-1", [{"type": "WITHDRAW", "amount": 20}], expected_version=0)
