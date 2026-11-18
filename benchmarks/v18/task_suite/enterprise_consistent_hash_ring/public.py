import unittest
from hash_ring import ConsistentHashRing

class Public(unittest.TestCase):
    def test_consistent_key_lookup(self):
        ring = ConsistentHashRing(vnodes=50)
        ring.add_node("node-A")
        ring.add_node("node-B")
        node1 = ring.get_node("user:1001")
        node2 = ring.get_node("user:1001")
        self.assertEqual(node1, node2)

    def test_minimal_key_relocation_on_node_addition(self):
        # In a 3-node ring, adding a 4th node should only relocate ~25% (1 / 4) of keys.
        # Naive modulo relocates ~75% of keys.
        ring = ConsistentHashRing(vnodes=100)
        ring.add_node("node-1")
        ring.add_node("node-2")
        ring.add_node("node-3")

        keys = [f"entity-key-{i}" for i in range(200)]
        initial_placement = {k: ring.get_node(k) for k in keys}

        # Add 4th node
        ring.add_node("node-4")
        new_placement = {k: ring.get_node(k) for k in keys}

        relocated = sum(1 for k in keys if initial_placement[k] != new_placement[k])
        relocation_fraction = relocated / len(keys)

        # Consistent hash ring ensures relocation fraction is close to 1/4 (at most 40%)
        # Naive modulo hashing would relocate ~75%
        self.assertLess(relocation_fraction, 0.40, f"Excessive key relocation: {relocation_fraction:.2%}")
