class InventoryService:
    def __init__(self):
        self.reserved = []
    def reserve(self, item_id):
        self.reserved.append(item_id)
        return f"reserved:{item_id}"
    def cancel(self, item_id):
        if item_id in self.reserved:
            self.reserved.remove(item_id)

class PaymentService:
    def __init__(self):
        self.charges = []
    def charge(self, amount):
        if amount > 1000:
            raise ValueError("Credit limit exceeded")
        self.charges.append(amount)
        return f"charged:{amount}"
    def refund(self, amount):
        if amount in self.charges:
            self.charges.remove(amount)

class ShipmentService:
    def __init__(self):
        self.shipments = []
    def schedule(self, item_id):
        self.shipments.append(item_id)
        return f"shipped:{item_id}"
    def cancel_shipment(self, item_id):
        if item_id in self.shipments:
            self.shipments.remove(item_id)
