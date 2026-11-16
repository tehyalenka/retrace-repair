from ledger_store import LedgerStore

class EventLog:
    def __init__(self, store=None):
        self.store = store if store is not None else LedgerStore()

    def append(self, event_id, account, delta):
        raise NotImplementedError

    def balance(self, account):
        raise NotImplementedError
