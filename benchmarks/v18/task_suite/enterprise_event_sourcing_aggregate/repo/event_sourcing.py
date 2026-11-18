class OptimisticConcurrencyError(Exception):
    pass

class EventStore:
    def __init__(self):
        self.streams = {}

    def get_events(self, stream_id, after_version=0):
        stream = self.streams.get(stream_id, [])
        return [e for e in stream if e["version"] > after_version]

    def get_version(self, stream_id):
        stream = self.streams.get(stream_id, [])
        return stream[-1]["version"] if stream else 0

    def append_events(self, stream_id, events, expected_version):
        # Buggy repo: Blindly appends events without checking expected_version!
        if stream_id not in self.streams:
            self.streams[stream_id] = []

        current_version = len(self.streams[stream_id])
        for i, ev in enumerate(events):
            versioned_ev = dict(ev)
            versioned_ev["version"] = current_version + i + 1
            self.streams[stream_id].append(versioned_ev)
        return len(self.streams[stream_id])

class BankAccountAggregate:
    def __init__(self, account_id):
        self.account_id = account_id
        self.balance = 0
        self.version = 0
        self.changes = []

    def deposit(self, amount):
        if amount <= 0:
            raise ValueError("Amount must be positive")
        self._apply_change({"type": "DEPOSIT", "amount": amount})

    def withdraw(self, amount):
        if amount <= 0:
            raise ValueError("Amount must be positive")
        if self.balance < amount:
            raise ValueError("Insufficient balance")
        self._apply_change({"type": "WITHDRAW", "amount": amount})

    def _apply_change(self, event):
        self._mutate(event)
        self.changes.append(event)

    def _mutate(self, event):
        if event["type"] == "DEPOSIT":
            self.balance += event["amount"]
        elif event["type"] == "WITHDRAW":
            self.balance -= event["amount"]

    def load_from_history(self, events):
        for ev in events:
            self._mutate(ev)
            self.version = ev["version"]
        self.changes = []
