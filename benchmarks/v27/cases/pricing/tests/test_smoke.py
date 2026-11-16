import unittest
from catalog import Catalog
from orders import OrderService
from discounts import DiscountRules
class Smoke(unittest.TestCase):
    def test_import(self):
        self.assertIsNotNone(OrderService(Catalog({}), DiscountRules({})))
