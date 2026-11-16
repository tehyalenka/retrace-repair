class Pricing:
    def __init__(self, prices, discounts=None):
        self.prices = dict(prices)
        self.discounts = dict(discounts or {})

    def calculate(self, items, coupon=None):
        """Return the final total in integer cents."""
        raise NotImplementedError
