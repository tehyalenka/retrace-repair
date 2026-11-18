class StaleEpochError(Exception):
    pass

class NotLeaderError(Exception):
    pass

class LeaderEpochCoordinator:
    def __init__(self):
        self.current_epoch = 0
        self.current_leader = None
        self.state = {}

    def elect_leader(self, node_id):
        if not node_id or not isinstance(node_id, str):
            raise ValueError("node_id must be non-empty string")
        self.current_epoch += 1
        self.current_leader = node_id
        return True, self.current_epoch

    def execute_write(self, node_id, epoch, key, value):
        if not node_id or not isinstance(node_id, str):
            raise ValueError("node_id must be non-empty string")
        if not isinstance(epoch, int) or epoch < 1:
            raise ValueError("epoch must be positive int")
        if not key or not isinstance(key, str):
            raise ValueError("key must be non-empty string")

        if epoch < self.current_epoch:
            raise StaleEpochError(
                f"Fencing reject: write presented stale epoch {epoch}, active epoch is {self.current_epoch}"
            )
        if epoch > self.current_epoch:
            raise StaleEpochError(
                f"Invalid epoch: write presented future epoch {epoch}, active epoch is {self.current_epoch}"
            )

        if node_id != self.current_leader:
            raise NotLeaderError(
                f"Node '{node_id}' is not the current leader (current leader: '{self.current_leader}')"
            )

        self.state[key] = value
        return True
