class OrderService:
    def __init__(self, catalog, discounts):
        self.catalog = catalog
        self.discounts = discounts

    def checkout(self, customer, items, coupon=None):
        raise NotImplementedError
