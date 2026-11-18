import unittest
from leader_election import LeaderEpochCoordinator, StaleEpochError, NotLeaderError

class Heldout(unittest.TestCase):
    def test_non_leader_node_rejected_in_current_epoch(self):
        coord = LeaderEpochCoordinator()
        _, epoch = coord.elect_leader("leader-1")

        with self.assertRaises(NotLeaderError):
            coord.execute_write("follower-2", epoch, "key", "val")

    def test_epoch_monotonicity_across_multiple_elections(self):
        coord = LeaderEpochCoordinator()
        epochs = []
        for i in range(5):
            _, ep = coord.elect_leader(f"node-{i}")
            epochs.append(ep)

        self.assertEqual(epochs, [1, 2, 3, 4, 5])
        # Only node-4 can write with epoch 5
        self.assertTrue(coord.execute_write("node-4", 5, "k", "v"))

        # All earlier nodes 0..3 fail with StaleEpochError
        for i in range(4):
            with self.assertRaises(StaleEpochError):
                coord.execute_write(f"node-{i}", i + 1, "k", "bad")

    def test_invalid_parameters_raise_value_error(self):
        coord = LeaderEpochCoordinator()
        with self.assertRaises(ValueError):
            coord.elect_leader("")
        coord.elect_leader("n1")
        with self.assertRaises(ValueError):
            coord.execute_write("", 1, "k", "v")
        with self.assertRaises(ValueError):
            coord.execute_write("n1", 0, "k", "v")
        with self.assertRaises(ValueError):
            coord.execute_write("n1", 1, "", "v")
