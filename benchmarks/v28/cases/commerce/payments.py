class Payments:
    def __init__(self):
        self.charges = {}

    def charge(self, order_id, amount, approved=True):
        """Charge an order at most once."""
        raise NotImplementedError
