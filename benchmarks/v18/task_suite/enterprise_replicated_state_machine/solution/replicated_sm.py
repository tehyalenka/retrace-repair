class QuorumNotReachedError(Exception):
    pass

class ReplicaNode:
    def __init__(self, node_id, is_online=True):
        self.node_id = node_id
        self.is_online = is_online
        self.log = []

    def append_entry(self, entry):
        if self.is_online:
            self.log.append(dict(entry))
            return True
        return False

class QuorumReplicatedStateMachine:
    def __init__(self, replicas):
        if not replicas:
            raise ValueError("Replicas list cannot be empty")
        self.replicas = list(replicas)
        self.quorum_size = (len(self.replicas) // 2) + 1
        self.commit_index = 0
        self.state = {}
        self.log = []

    def propose(self, key, value):
        if not key or not isinstance(key, str):
            raise ValueError("key must be non-empty string")

        # Roll back any uncommitted log entries from previous failed proposals
        if len(self.log) > self.commit_index:
            self.log = self.log[:self.commit_index]

        entry_idx = len(self.log) + 1
        entry = {"index": entry_idx, "key": key, "value": value}
        self.log.append(entry)

        acks = 0
        for r in self.replicas:
            if r.append_entry(entry):
                acks += 1

        if acks < self.quorum_size:
            # Quorum not reached: do NOT commit or apply to state machine
            return False

        # Quorum confirmed: apply committed entries up to entry_idx
        for idx in range(self.commit_index, entry_idx):
            e = self.log[idx]
            self.state[e["key"]] = e["value"]

        self.commit_index = entry_idx
        return True

    def get(self, key):
        return self.state.get(key)
