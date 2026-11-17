import unittest
from saga import SagaCoordinator, SagaExecutionError

class Heldout(unittest.TestCase):
    def test_reverse_order_compensation(self):
        order_of_compensation = []
        saga = SagaCoordinator()
        saga.add_step("step1", lambda ctx: "out1", lambda ctx: order_of_compensation.append("comp1"))
        saga.add_step("step2", lambda ctx: "out2", lambda ctx: order_of_compensation.append("comp2"))
        saga.add_step("step3", lambda ctx: (_ for _ in ()).throw(RuntimeError("step3 fail")), lambda ctx: order_of_compensation.append("comp3"))

        with self.assertRaises(SagaExecutionError) as cm:
            saga.execute({})

        self.assertEqual(cm.exception.failed_step, "step3")
        # Step 3 itself failed so it is not compensated; steps 2 and 1 are compensated in REVERSE order
        self.assertEqual(order_of_compensation, ["comp2", "comp1"])
        self.assertEqual(cm.exception.compensated_steps, ["step2", "step1"])

    def test_invalid_step_registration(self):
        saga = SagaCoordinator()
        with self.assertRaises(ValueError):
            saga.add_step("", lambda ctx: 1, lambda ctx: 1)
        with self.assertRaises(ValueError):
            saga.add_step("s1", "not_callable", lambda ctx: 1)
        with self.assertRaises(ValueError):
            saga.add_step("s1", lambda ctx: 1, "not_callable")

        saga.add_step("step1", lambda ctx: 1, lambda ctx: 1)
        with self.assertRaises(ValueError):
            saga.add_step("step1", lambda ctx: 2, lambda ctx: 2)

    def test_saga_success_returns_results(self):
        saga = SagaCoordinator()
        saga.add_step("s1", lambda ctx: ctx["x"] * 2, lambda ctx: None)
        saga.add_step("s2", lambda ctx: ctx["x"] + 10, lambda ctx: None)
        res = saga.execute({"x": 5})
        self.assertIsInstance(res, dict)
        self.assertIs(res.get("success"), True)
        self.assertEqual(res.get("results"), {"s1": 10, "s2": 15})
