class OptimisticConcurrencyError(Exception):
    pass

class EventStore:
    def __init__(self):
        self.streams = {}

    def get_events(self, stream_id, after_version=0):
        if not stream_id or not isinstance(stream_id, str):
            raise ValueError("stream_id must be non-empty string")
        stream = self.streams.get(stream_id, [])
        return [e for e in stream if e["version"] > after_version]

    def get_version(self, stream_id):
        stream = self.streams.get(stream_id, [])
        return stream[-1]["version"] if stream else 0

    def append_events(self, stream_id, events, expected_version):
        if not stream_id or not isinstance(stream_id, str):
            raise ValueError("stream_id must be non-empty string")
        if not isinstance(expected_version, int) or expected_version < 0:
            raise ValueError("expected_version must be non-negative integer")

        if stream_id not in self.streams:
            self.streams[stream_id] = []

        current_version = len(self.streams[stream_id])
        if current_version != expected_version:
            raise OptimisticConcurrencyError(
                f"Stream '{stream_id}' version mismatch: expected {expected_version}, but found {current_version}"
            )

        for i, ev in enumerate(events):
            versioned_ev = dict(ev)
            versioned_ev["version"] = current_version + i + 1
            self.streams[stream_id].append(versioned_ev)

        return len(self.streams[stream_id])

class BankAccountAggregate:
    def __init__(self, account_id):
        if not account_id or not isinstance(account_id, str):
            raise ValueError("account_id must be non-empty string")
        self.account_id = account_id
        self.balance = 0
        self.version = 0
        self.changes = []

    def deposit(self, amount):
        if not isinstance(amount, (int, float)) or isinstance(amount, bool) or amount <= 0:
            raise ValueError("Amount must be positive number")
        self._apply_change({"type": "DEPOSIT", "amount": amount})

    def withdraw(self, amount):
        if not isinstance(amount, (int, float)) or isinstance(amount, bool) or amount <= 0:
            raise ValueError("Amount must be positive number")
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

    def take_snapshot(self):
        return {
            "account_id": self.account_id,
            "balance": self.balance,
            "version": self.version
        }

    def load_from_snapshot(self, snapshot):
        if snapshot["account_id"] != self.account_id:
            raise ValueError("Mismatched account_id in snapshot")
        self.balance = snapshot["balance"]
        self.version = snapshot["version"]
        self.changes = []
