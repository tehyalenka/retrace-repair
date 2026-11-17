class PaymentGateway:
    def __init__(self, decline=False):
        self.decline = decline
        self.charges = []

    def charge(self, order_id, amount):
        if self.decline:
            return False
        self.charges.append((order_id, amount))
        return True
