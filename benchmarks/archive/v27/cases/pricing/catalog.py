class Catalog:
    def __init__(self, prices):
        self.prices = dict(prices)

    def quote(self, items):
        raise NotImplementedError
