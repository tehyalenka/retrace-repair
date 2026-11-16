from models import LineItem, Receipt

class OrderService:
    def __init__(self, inventory, pricing, payments, audit):
        self.inventory = inventory
        self.pricing = pricing
        self.payments = payments
        self.audit = audit
        self.orders = {}

    def checkout(self, order_id, items, coupon=None, approved=True):
        """Coordinate a complete atomic checkout."""
        raise NotImplementedError
