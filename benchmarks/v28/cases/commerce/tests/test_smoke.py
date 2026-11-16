import unittest

from models import LineItem, Receipt
from inventory import Inventory
from pricing import Pricing
from payments import Payments
from audit import AuditLog
from orders import OrderService

class SmokeTests(unittest.TestCase):
    def test_imports(self):
        self.assertTrue(LineItem)
        self.assertTrue(Receipt)
        self.assertTrue(Inventory)
        self.assertTrue(Pricing)
        self.assertTrue(Payments)
        self.assertTrue(AuditLog)
        self.assertTrue(OrderService)

if __name__ == "__main__":
    unittest.main()
