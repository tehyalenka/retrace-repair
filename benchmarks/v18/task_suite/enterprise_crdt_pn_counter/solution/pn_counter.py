class PNCounter:
    """State-based Positive-Negative Counter CRDT."""
    def __init__(self, node_id):
        if not node_id or not isinstance(node_id, str):
            raise ValueError("node_id must be non-empty string")
        self.node_id = node_id
        self.P = {node_id: 0}
        self.N = {node_id: 0}

    def increment(self, delta=1):
        if not isinstance(delta, int) or isinstance(delta, bool) or delta <= 0:
            raise ValueError("delta must be positive integer")
        self.P[self.node_id] = self.P.get(self.node_id, 0) + delta

    def decrement(self, delta=1):
        if not isinstance(delta, int) or isinstance(delta, bool) or delta <= 0:
            raise ValueError("delta must be positive integer")
        self.N[self.node_id] = self.N.get(self.node_id, 0) + delta

    def value(self):
        return sum(self.P.values()) - sum(self.N.values())

    def merge(self, other):
        if not isinstance(other, PNCounter):
            raise ValueError("Can only merge with another PNCounter instance")

        all_nodes_p = set(self.P.keys()) | set(other.P.keys())
        for n in all_nodes_p:
            self.P[n] = max(self.P.get(n, 0), other.P.get(n, 0))

        all_nodes_n = set(self.N.keys()) | set(other.N.keys())
        for n in all_nodes_n:
            self.N[n] = max(self.N.get(n, 0), other.N.get(n, 0))

    def copy(self):
        c = PNCounter(self.node_id)
        c.P = dict(self.P)
        c.N = dict(self.N)
        return c
