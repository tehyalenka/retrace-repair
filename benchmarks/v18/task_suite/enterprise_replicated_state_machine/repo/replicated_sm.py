class QuorumNotReachedError(Exception):
    pass

class ReplicaNode:
    def __init__(self, node_id, is_online=True):
        self.node_id = node_id
        self.is_online = is_online
        self.log = []

    def append_entry(self, entry):
        if self.is_online:
            self.log.append(entry)
            return True
        return False

class QuorumReplicatedStateMachine:
    def __init__(self, replicas):
        self.replicas = list(replicas) # list of ReplicaNode
        self.quorum_size = (len(self.replicas) // 2) + 1
        self.commit_index = 0
        self.state = {}
        self.log = []

    def propose(self, key, value):
        entry_idx = len(self.log) + 1
        entry = {"index": entry_idx, "key": key, "value": value}
        self.log.append(entry)

        # Buggy repo: mutates state machine BEFORE checking quorum!
        self.state[key] = value

        # Check replication
        acks = 0
        for r in self.replicas:
            if r.append_entry(entry):
                acks += 1

        if acks < self.quorum_size:
            # Bug: already mutated state!
            return False

        self.commit_index = entry_idx
        return True
