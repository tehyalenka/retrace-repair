import unittest

from models import LineItem, Receipt
from inventory import Inventory
from pricing import Pricing
from payments import Payments
from audit import AuditLog
from orders import OrderService


class CommerceVerification(unittest.TestCase):

    def setUp(self):
        self.inventory = Inventory({"A": 10, "B": 5})
        self.pricing = Pricing(
            {"A": 1000, "B": 500},
            {"SAVE10": 10, "FREE": 100}
        )
        self.payments = Payments()
        self.audit = AuditLog()
        self.service = OrderService(
            self.inventory,
            self.pricing,
            self.payments,
            self.audit
        )

    def items(self, *entries):
        return [LineItem(*entry) for entry in entries]

    def test_01_receipt_immutable(self):
        receipt = Receipt("o1", 100, "paid")
        with self.assertRaises(Exception):
            receipt.total = 200

    def test_02_inventory_success(self):
        self.inventory.reserve(self.items(("A", 2)))
        self.assertEqual(self.inventory.available("A"), 8)

    def test_03_inventory_duplicate_skus(self):
        self.inventory.reserve(
            self.items(("A", 2), ("A", 3))
        )
        self.assertEqual(self.inventory.available("A"), 5)

    def test_04_inventory_insufficient_atomic(self):
        before = dict(self.inventory.stock)
        with self.assertRaises(ValueError):
            self.inventory.reserve(
                self.items(("A", 2), ("B", 99))
            )
        self.assertEqual(self.inventory.stock, before)

    def test_05_inventory_invalid_atomic(self):
        before = dict(self.inventory.stock)
        for items in [
            [],
            self.items(("A", 0)),
            self.items(("A", -1)),
            self.items(("UNKNOWN", 1)),
            self.items(("A", True)),
        ]:
            with self.assertRaises(ValueError):
                self.inventory.reserve(items)
            self.assertEqual(self.inventory.stock, before)

    def test_06_pricing_basic(self):
        self.assertEqual(
            self.pricing.calculate(
                self.items(("A", 2), ("B", 1))
            ),
            2500
        )

    def test_07_pricing_duplicates(self):
        self.assertEqual(
            self.pricing.calculate(
                self.items(("A", 1), ("A", 2))
            ),
            3000
        )

    def test_08_pricing_coupon(self):
        self.assertEqual(
            self.pricing.calculate(
                self.items(("A", 2)), "SAVE10"
            ),
            1800
        )

    def test_09_pricing_invalid_coupon(self):
        with self.assertRaises(ValueError):
            self.pricing.calculate(
                self.items(("A", 1)), "INVALID"
            )

    def test_10_pricing_invalid_discount(self):
        pricing = Pricing({"A": 100}, {"BAD": 120})
        with self.assertRaises(ValueError):
            pricing.calculate(
                self.items(("A", 1)), "BAD"
            )

    def test_11_payment_success(self):
        self.assertEqual(
            self.payments.charge("o1", 1000),
            1000
        )
        self.assertEqual(self.payments.charges["o1"], 1000)

    def test_12_payment_idempotency(self):
        self.payments.charge("o1", 1000)
        self.assertEqual(
            self.payments.charge("o1", 1000),
            1000
        )
        self.assertEqual(len(self.payments.charges), 1)

    def test_13_payment_conflict(self):
        self.payments.charge("o1", 1000)
        with self.assertRaises(ValueError):
            self.payments.charge("o1", 2000)

    def test_14_payment_decline(self):
        with self.assertRaises(ValueError):
            self.payments.charge("o1", 1000, approved=False)
        self.assertEqual(self.payments.charges, {})

    def test_15_audit_idempotency(self):
        self.audit.record("o1", 1000)
        self.audit.record("o1", 1000)
        self.assertEqual(len(self.audit.events), 1)

    def test_16_audit_conflict(self):
        self.audit.record("o1", 1000)
        with self.assertRaises(ValueError):
            self.audit.record("o1", 2000)
        self.assertEqual(len(self.audit.events), 1)

    def test_17_checkout_success(self):
        receipt = self.service.checkout(
            "o1", self.items(("A", 2), ("B", 1))
        )
        self.assertEqual(receipt, Receipt("o1", 2500, "paid"))
        self.assertEqual(self.inventory.stock["A"], 8)
        self.assertEqual(self.inventory.stock["B"], 4)
        self.assertEqual(self.payments.charges["o1"], 2500)
        self.assertEqual(len(self.audit.events), 1)

    def test_18_checkout_coupon(self):
        receipt = self.service.checkout(
            "o1", self.items(("A", 2)), "SAVE10"
        )
        self.assertEqual(receipt.total, 1800)

    def test_19_checkout_idempotency(self):
        first = self.service.checkout(
            "o1", self.items(("A", 2))
        )
        second = self.service.checkout(
            "o1", self.items(("A", 2))
        )
        self.assertEqual(first, second)
        self.assertEqual(self.inventory.stock["A"], 8)
        self.assertEqual(len(self.payments.charges), 1)
        self.assertEqual(len(self.audit.events), 1)

    def test_20_checkout_decline_atomic(self):
        before = dict(self.inventory.stock)
        with self.assertRaises(ValueError):
            self.service.checkout(
                "o1", self.items(("A", 2)),
                approved=False
            )
        self.assertEqual(self.inventory.stock, before)
        self.assertEqual(self.payments.charges, {})
        self.assertEqual(self.audit.events, [])
        self.assertEqual(self.service.orders, {})

    def test_21_checkout_insufficient_atomic(self):
        before = dict(self.inventory.stock)
        with self.assertRaises(ValueError):
            self.service.checkout(
                "o1", self.items(("A", 99))
            )
        self.assertEqual(self.inventory.stock, before)
        self.assertEqual(self.payments.charges, {})
        self.assertEqual(self.audit.events, [])

    def test_22_checkout_invalid_atomic(self):
        with self.assertRaises(ValueError):
            self.service.checkout(
                "o1", self.items(("A", 0))
            )
        self.assertEqual(self.inventory.stock["A"], 10)
        self.assertEqual(self.payments.charges, {})
        self.assertEqual(self.audit.events, [])

    def test_23_checkout_duplicate_items(self):
        receipt = self.service.checkout(
            "o1",
            self.items(("A", 2), ("A", 3))
        )
        self.assertEqual(receipt.total, 5000)
        self.assertEqual(self.inventory.stock["A"], 5)

    def test_24_checkout_unknown_coupon_atomic(self):
        with self.assertRaises(ValueError):
            self.service.checkout(
                "o1", self.items(("A", 1)), "INVALID"
            )
        self.assertEqual(self.inventory.stock["A"], 10)
        self.assertEqual(self.payments.charges, {})
        self.assertEqual(self.audit.events, [])


    def test_25_payment_exception_rollback(self):
        def fail(*args, **kwargs):
            raise RuntimeError("Payment service unavailable")

        self.payments.charge = fail

        before = dict(self.inventory.stock)

        with self.assertRaises(RuntimeError):
            self.service.checkout("o1", self.items(("A", 2)))

        self.assertEqual(self.inventory.stock, before)
        self.assertEqual(self.payments.charges, {})
        self.assertEqual(self.audit.events, [])
        self.assertEqual(self.service.orders, {})

    def test_26_inventory_exception_rollback(self):
        original = self.inventory.reserve

        def fail_after_reservation(items):
            original(items)
            raise RuntimeError("Inventory persistence failure")

        self.inventory.reserve = fail_after_reservation

        before = dict(self.inventory.stock)

        with self.assertRaises(RuntimeError):
            self.service.checkout("o1", self.items(("A", 2)))

        self.assertEqual(self.inventory.stock, before)
        self.assertEqual(self.payments.charges, {})
        self.assertEqual(self.audit.events, [])
        self.assertEqual(self.service.orders, {})

    def test_27_audit_exception_rollback(self):
        original = self.audit.record

        def fail_after_record(order_id, total):
            original(order_id, total)
            raise RuntimeError("Audit persistence failure")

        self.audit.record = fail_after_record

        before = dict(self.inventory.stock)

        with self.assertRaises(RuntimeError):
            self.service.checkout("o1", self.items(("A", 2)))

        self.assertEqual(self.inventory.stock, before)
        self.assertEqual(self.payments.charges, {})
        self.assertEqual(self.audit.events, [])
        self.assertEqual(self.service.orders, {})

    def test_28_successful_retry_after_failure(self):
        original = self.audit.record

        def fail_once(order_id, total):
            self.audit.record = original
            raise RuntimeError("Temporary audit failure")

        self.audit.record = fail_once

        with self.assertRaises(RuntimeError):
            self.service.checkout("o1", self.items(("A", 2)))

        receipt = self.service.checkout(
            "o1", self.items(("A", 2))
        )

        self.assertEqual(receipt.total, 2000)
        self.assertEqual(self.inventory.stock["A"], 8)
        self.assertEqual(self.payments.charges["o1"], 2000)
        self.assertEqual(len(self.audit.events), 1)


if __name__ == "__main__":
    unittest.main()
