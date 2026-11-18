import unittest
from replicated_sm import QuorumReplicatedStateMachine, ReplicaNode

class Heldout(unittest.TestCase):
    def test_uncommitted_entry_overwritten_on_subsequent_proposal(self):
        r1 = ReplicaNode("n1", is_online=True)
        r2 = ReplicaNode("n2", is_online=False)
        r3 = ReplicaNode("n3", is_online=False)

        sm = QuorumReplicatedStateMachine([r1, r2, r3])
        # Attempt 1 fails quorum
        self.assertFalse(sm.propose("counter", "100"))
        self.assertEqual(sm.commit_index, 0)

        # Node 2 comes online, quorum restored
        r2.is_online = True
        self.assertTrue(sm.propose("counter", "200"))
        self.assertEqual(sm.commit_index, 1)
        self.assertEqual(sm.get("counter"), "200")
        self.assertEqual(len(sm.log), 1)
        self.assertEqual(sm.log[0]["value"], "200")

    def test_sequential_linear_commit_progression(self):
        replicas = [ReplicaNode(f"r{i}", is_online=True) for i in range(3)]
        sm = QuorumReplicatedStateMachine(replicas)

        for i in range(5):
            self.assertTrue(sm.propose(f"k{i}", f"v{i}"))
            self.assertEqual(sm.commit_index, i + 1)
            self.assertEqual(sm.get(f"k{i}"), f"v{i}")

    def test_invalid_parameters_raise_value_error(self):
        with self.assertRaises(ValueError):
            QuorumReplicatedStateMachine([])
        sm = QuorumReplicatedStateMachine([ReplicaNode("n1")])
        with self.assertRaises(ValueError):
            sm.propose("", "val")
