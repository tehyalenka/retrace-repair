import unittest
from hash_ring import ConsistentHashRing

class Heldout(unittest.TestCase):
    def test_node_removal_relocates_only_removed_node_keys(self):
        ring = ConsistentHashRing(vnodes=100)
        ring.add_node("n1"); ring.add_node("n2"); ring.add_node("n3")

        keys = [f"k-{i}" for i in range(150)]
        initial = {k: ring.get_node(k) for k in keys}

        # Remove n2
        ring.remove_node("n2")
        after = {k: ring.get_node(k) for k in keys}

        for k in keys:
            if initial[k] != "n2":
                # Keys that were originally on n1 or n3 MUST NOT move!
                self.assertEqual(after[k], initial[k], f"Key {k} moved despite not belonging to removed node!")
            else:
                # Keys that were on n2 must now be on n1 or n3
                self.assertIn(after[k], ("n1", "n3"))

    def test_empty_ring_raises_key_error(self):
        ring = ConsistentHashRing()
        with self.assertRaises(KeyError):
            ring.get_node("k")

    def test_invalid_parameters_raise_value_error(self):
        with self.assertRaises(ValueError):
            ConsistentHashRing(vnodes=0)
        ring = ConsistentHashRing()
        with self.assertRaises(ValueError):
            ring.add_node("")
        ring.add_node("n1")
        with self.assertRaises(ValueError):
            ring.get_node("")
