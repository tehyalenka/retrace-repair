import unittest
from pn_counter import PNCounter

class Public(unittest.TestCase):
    def test_single_replica_increment_decrement(self):
        c = PNCounter("node-1")
        c.increment(10)
        c.decrement(3)
        self.assertEqual(c.value(), 7)

    def test_merge_idempotency(self):
        c1 = PNCounter("node-1")
        c1.increment(5)

        c2 = PNCounter("node-2")
        c2.increment(3)

        # Merge c2 into c1
        c1.merge(c2)
        self.assertEqual(c1.value(), 8)

        # Idempotent re-merge: merging c2 again must NOT change the value
        c1.merge(c2)
        self.assertEqual(c1.value(), 8)

        # Self-merge must be a no-op
        c1.merge(c1)
        self.assertEqual(c1.value(), 8)
