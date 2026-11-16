class Ledger:
    def __init__(self):
        self.charges = {}
        self.refunds = {}

    def charge(self, booking_id, amount):
        self.charges[booking_id] = amount

    def refund(self, booking_id, amount):
        self.refunds[booking_id] = self.refunds.get(booking_id, 0) + amount
