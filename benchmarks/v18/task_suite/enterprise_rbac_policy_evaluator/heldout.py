import unittest
from rbac import RBACPolicyEngine, CyclicRoleInheritanceError

class Heldout(unittest.TestCase):
    def test_cyclic_role_inheritance_rejected(self):
        engine = RBACPolicyEngine()
        engine.add_role("A")
        engine.add_role("B", parents=["A"])
        engine.add_role("C", parents=["B"])

        # Creating cycle A -> C (since C already inherits from B which inherits from A)
        with self.assertRaises(CyclicRoleInheritanceError):
            engine.add_role("A", parents=["C"])

    def test_deny_by_default(self):
        engine = RBACPolicyEngine()
        engine.add_role("guest")
        engine.assign_user_role("charlie", "guest")
        # Unassigned permission denies
        self.assertFalse(engine.evaluate("charlie", "delete:database"))
        # Unknown user denies
        self.assertFalse(engine.evaluate("unknown_user", "read:document"))

    def test_invalid_parameters_raise_value_error(self):
        engine = RBACPolicyEngine()
        with self.assertRaises(ValueError):
            engine.add_role("")
        with self.assertRaises(ValueError):
            engine.assign_permission("r", "p", effect="MAYBE")
        with self.assertRaises(ValueError):
            engine.assign_user_role("u", "nonexistent_role")
