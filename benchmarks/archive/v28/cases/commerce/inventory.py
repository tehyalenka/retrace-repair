class Inventory:
    def __init__(self, stock):
        self.stock = dict(stock)

    def available(self, sku):
        return self.stock.get(sku, 0)

    def reserve(self, items):
        """Reserve inventory atomically."""
        raise NotImplementedError
