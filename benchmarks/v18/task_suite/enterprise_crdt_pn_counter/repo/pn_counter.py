class PNCounter:
    """State-based Positive-Negative Counter CRDT."""
    def __init__(self, node_id):
        self.node_id = node_id
        self.P = {node_id: 0}
        self.N = {node_id: 0}

    def increment(self, delta=1):
        if delta <= 0:
            raise ValueError("delta must be positive")
        self.P[self.node_id] = self.P.get(self.node_id, 0) + delta

    def decrement(self, delta=1):
        if delta <= 0:
            raise ValueError("delta must be positive")
        self.N[self.node_id] = self.N.get(self.node_id, 0) + delta

    def value(self):
        return sum(self.P.values()) - sum(self.N.values())

    def merge(self, other):
        # Buggy repo: Sums the vectors instead of taking component-wise maximum!
        # Violates idempotence: merging with self doubles the counts!
        all_nodes = set(self.P.keys()) | set(other.P.keys())
        for n in all_nodes:
            self.P[n] = self.P.get(n, 0) + other.P.get(n, 0)
        
        all_nodes_n = set(self.N.keys()) | set(other.N.keys())
        for n in all_nodes_n:
            self.N[n] = self.N.get(n, 0) + other.N.get(n, 0)
