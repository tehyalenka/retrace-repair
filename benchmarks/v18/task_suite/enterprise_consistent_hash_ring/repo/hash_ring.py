import hashlib

class ConsistentHashRing:
    def __init__(self, vnodes=50):
        self.vnodes = vnodes
        self.nodes = []

    def add_node(self, node):
        if node not in self.nodes:
            self.nodes.append(node)
            self.nodes.sort()

    def remove_node(self, node):
        if node in self.nodes:
            self.nodes.remove(node)

    def get_node(self, key):
        if not self.nodes:
            raise KeyError("No nodes in ring")
        
        # Buggy repo: Naive modulo hashing!
        # Causes catastrophic ~75% key churn when adding a 4th node to a 3-node ring!
        h = int(hashlib.md5(key.encode('utf-8')).hexdigest(), 16)
        return self.nodes[h % len(self.nodes)]
