import unittest
from replicated_sm import QuorumReplicatedStateMachine, ReplicaNode

class Public(unittest.TestCase):
    def test_quorum_write_succeeds(self):
        # 3 replicas, quorum = 2
        r1 = ReplicaNode("n1", is_online=True)
        r2 = ReplicaNode("n2", is_online=True)
        r3 = ReplicaNode("n3", is_online=False) # 1 offline, 2 online -> quorum met!

        sm = QuorumReplicatedStateMachine([r1, r2, r3])
        ok = sm.propose("user:1", "active")
        self.assertTrue(ok)
        self.assertEqual(sm.get("user:1"), "active")
        self.assertEqual(sm.commit_index, 1)

    def test_missing_quorum_does_not_mutate_state(self):
        # 3 replicas, quorum = 2. Only 1 is online.
        r1 = ReplicaNode("n1", is_online=True)
        r2 = ReplicaNode("n2", is_online=False)
        r3 = ReplicaNode("n3", is_online=False)

        sm = QuorumReplicatedStateMachine([r1, r2, r3])
        ok = sm.propose("user:2", "compromised")

        # Must fail because only 1 of 2 required quorum replicas acknowledged
        self.assertFalse(ok)
        # Crucial invariant: state MUST NOT be updated if quorum was not reached!
        self.assertIsNone(sm.get("user:2"), "State machine mutated without reaching quorum!")
        self.assertEqual(sm.commit_index, 0)
