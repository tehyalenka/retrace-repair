class LedgerStore:
    def __init__(self):
        self.events = []
    def append(self, event):
        self.events.append(dict(event))
    def all(self):
        return list(self.events)
