class Inventory:
    def __init__(self, stock, prices):
        self.stock = dict(stock)
        self.prices = dict(prices)

    def available(self, sku):
        return self.stock.get(sku, 0)
