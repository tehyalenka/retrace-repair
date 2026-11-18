import unittest
from leader_election import LeaderEpochCoordinator, StaleEpochError

class Public(unittest.TestCase):
    def test_active_leader_write(self):
        coord = LeaderEpochCoordinator()
        _, epoch = coord.elect_leader("node-A")
        self.assertEqual(epoch, 1)

        ok = coord.execute_write("node-A", epoch, "config:mode", "production")
        self.assertTrue(ok)
        self.assertEqual(coord.state["config:mode"], "production")

    def test_stale_epoch_split_brain_rejected(self):
        coord = LeaderEpochCoordinator()
        # Epoch 1: Node A elected leader
        _, epoch1 = coord.elect_leader("node-A")

        # Network partition occurs; majority elects Node B in Epoch 2
        _, epoch2 = coord.elect_leader("node-B")
        self.assertEqual(epoch2, 2)

        # Zombie Node A attempts write presenting stale epoch 1: MUST be fenced off!
        with self.assertRaises(StaleEpochError):
            coord.execute_write("node-A", epoch1, "config:mode", "split-brain-write")

        # State must remain untouched by zombie leader
        self.assertNotIn("config:mode", coord.state)
