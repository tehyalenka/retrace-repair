from inventory import Inventory
from orders import create_order

class Store:
    def __init__(self, stock):
        self.inventory = Inventory(stock)

    def purchase(self, items):
        return create_order(self.inventory, items)
