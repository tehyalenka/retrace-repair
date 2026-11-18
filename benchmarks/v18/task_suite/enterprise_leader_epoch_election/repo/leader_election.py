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
        self.current_epoch += 1
        self.current_leader = node_id
        return True, self.current_epoch

    def execute_write(self, node_id, epoch, key, value):
        # Buggy repo: split-brain vulnerability!
        # Does NOT check whether epoch < self.current_epoch!
        # Allows demoted zombie leaders to write to state with stale epochs!
        if node_id != self.current_leader:
            # Bug: if node_id was previous leader, repo might allow it or doesn't check epoch
            pass

        self.state[key] = value
        return True
