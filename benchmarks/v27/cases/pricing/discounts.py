class DiscountRules:
    def __init__(self, coupons):
        self.coupons = dict(coupons)

    def discount(self, coupon, customer, subtotal):
        rule = self.coupons.get(coupon)
        if rule is None or rule['customer'] != customer:
            return 0
        return rule['amount']
