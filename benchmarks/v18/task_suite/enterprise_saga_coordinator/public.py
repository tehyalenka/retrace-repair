import unittest
from saga import SagaCoordinator, SagaExecutionError
from services import InventoryService, PaymentService, ShipmentService

class Public(unittest.TestCase):
    def test_saga_success(self):
        inv = InventoryService()
        pay = PaymentService()
        saga = SagaCoordinator()
        saga.add_step("reserve", lambda ctx: inv.reserve(ctx["item"]), lambda ctx: inv.cancel(ctx["item"]))
        saga.add_step("charge", lambda ctx: pay.charge(ctx["amount"]), lambda ctx: pay.refund(ctx["amount"]))

        res = saga.execute({"item": "item-1", "amount": 100})
        self.assertTrue(res["success"])
        self.assertEqual(inv.reserved, ["item-1"])
        self.assertEqual(pay.charges, [100])

    def test_saga_failure_triggers_compensation(self):
        inv = InventoryService()
        pay = PaymentService()
        saga = SagaCoordinator()
        saga.add_step("reserve", lambda ctx: inv.reserve(ctx["item"]), lambda ctx: inv.cancel(ctx["item"]))
        # Fails because amount > 1000
        saga.add_step("charge", lambda ctx: pay.charge(ctx["amount"]), lambda ctx: pay.refund(ctx["amount"]))

        with self.assertRaises(SagaExecutionError) as cm:
            saga.execute({"item": "item-1", "amount": 5000})

        self.assertEqual(cm.exception.failed_step, "charge")
        self.assertEqual(cm.exception.compensated_steps, ["reserve"])
        # Inventory reservation must be rolled back by compensation
        self.assertEqual(inv.reserved, [])
