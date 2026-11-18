import unittest
from pn_counter import PNCounter

class Heldout(unittest.TestCase):
    def test_merge_commutativity(self):
        a1 = PNCounter("n1"); a1.increment(12); a1.decrement(4)
        b1 = PNCounter("n2"); b1.increment(7); b1.decrement(2)

        # Merge a1 <- b1
        m1 = a1.copy()
        m1.merge(b1)

        # Merge b1 <- a1
        m2 = b1.copy()
        m2.merge(a1)

        self.assertEqual(m1.value(), m2.value())
        self.assertEqual(m1.P, m2.P)
        self.assertEqual(m1.N, m2.N)

    def test_multi_node_cluster_eventual_consistency(self):
        nodes = [PNCounter(f"node-{i}") for i in range(4)]
        nodes[0].increment(10)
        nodes[1].decrement(4)
        nodes[2].increment(6)
        nodes[3].increment(1)

        # Gossip in ring
        for i in range(4):
            nodes[(i+1)%4].merge(nodes[i])
        for i in range(4):
            nodes[(i+1)%4].merge(nodes[i])

        # All nodes must converge to 10 - 4 + 6 + 1 = 13
        for n in nodes:
            self.assertEqual(n.value(), 13)

    def test_invalid_parameters_raise_value_error(self):
        c = PNCounter("node-1")
        with self.assertRaises(ValueError):
            c.increment(0)
        with self.assertRaises(ValueError):
            c.increment(-5)
        with self.assertRaises(ValueError):
            c.decrement("bad")
        with self.assertRaises(ValueError):
            c.merge("not a counter")
        with self.assertRaises(ValueError):
            PNCounter("")
