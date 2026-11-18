import hashlib
import bisect

class ConsistentHashRing:
    def __init__(self, vnodes=100):
        if not isinstance(vnodes, int) or isinstance(vnodes, bool) or vnodes <= 0:
            raise ValueError("vnodes must be positive integer")
        self.vnodes = vnodes
        self.nodes = set()
        self.ring = [] # sorted list of (hash_val, node)

    def _hash(self, val):
        return int(hashlib.md5(val.encode('utf-8')).hexdigest(), 16)

    def add_node(self, node):
        if not node or not isinstance(node, str):
            raise ValueError("node must be non-empty string")
        if node in self.nodes:
            return
        self.nodes.add(node)
        for i in range(self.vnodes):
            v_key = f"{node}#vn_{i}"
            h = self._hash(v_key)
            self.ring.append((h, node))
        self.ring.sort(key=lambda x: x[0])

    def remove_node(self, node):
        if node not in self.nodes:
            return
        self.nodes.remove(node)
        self.ring = [item for item in self.ring if item[1] != node]

    def get_node(self, key):
        if not self.ring:
            raise KeyError("No nodes in ring")
        if not key or not isinstance(key, str):
            raise ValueError("key must be non-empty string")

        h = self._hash(key)
        # Binary search for the first node with hash >= h
        keys = [item[0] for item in self.ring]
        idx = bisect.bisect_right(keys, h)
        if idx == len(self.ring):
            idx = 0 # Ring wraparound
        return self.ring[idx][1]
