import unittest
from catalog import Catalog
from orders import OrderService
from discounts import DiscountRules

class PricingVerification(unittest.TestCase):
    def setUp(self):
        self.catalog = Catalog({'a': 10, 'b': 7})
        self.rules = DiscountRules({'SAVE': {'customer': 'alice', 'amount': 5},
                                    'BAD': {'customer': 'alice', 'amount': 1000}})
        self.service = OrderService(self.catalog, self.rules)
    def test_quote_aggregation(self):
        self.assertEqual(self.catalog.quote([('a', 2), ('b', 1), ('a', 3)]), 57)
    def test_checkout_coupon(self):
        self.assertEqual(self.service.checkout('alice', [('a', 2)], 'SAVE'),
                         {'subtotal': 20, 'discount': 5, 'total': 15})
    def test_coupon_customer_scope(self):
        self.assertEqual(self.service.checkout('bob', [('a', 1)], 'SAVE')['total'], 10)
    def test_invalid_inputs(self):
        for items in ([], [('missing', 1)], [('a', 0)], [('a', True)], [('a', 1.5)]):
            with self.subTest(items=items), self.assertRaises(ValueError):
                self.catalog.quote(items)
    def test_invalid_discount(self):
        with self.assertRaises(ValueError):
            self.service.checkout('alice', [('a', 1)], 'BAD')
    def test_no_mutation(self):
        items = [('a', 1), ('a', 2)]
        self.service.checkout('alice', items)
        self.assertEqual(items, [('a', 1), ('a', 2)])
        self.assertEqual(self.catalog.prices, {'a': 10, 'b': 7})
        self.assertEqual(self.rules.coupons['SAVE']['amount'], 5)
