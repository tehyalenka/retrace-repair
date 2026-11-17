class AuditLog:
    def __init__(self):
        self.events = []

    def record(self, order_id, total):
        """Record a successful order exactly once."""
        raise NotImplementedError
