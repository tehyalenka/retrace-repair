from inventory import Inventory
from payments import PaymentGateway

class Checkout:
    def __init__(self, inventory, gateway):
        self.inventory = inventory
        self.gateway = gateway
        self.orders = {}

    def place(self, order_id, items):
        raise NotImplementedError
