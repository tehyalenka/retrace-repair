import unittest
from rbac import RBACPolicyEngine

class Public(unittest.TestCase):
    def test_role_inheritance_allow(self):
        engine = RBACPolicyEngine()
        engine.add_role("viewer")
        engine.assign_permission("viewer", "read:document", effect="ALLOW")

        engine.add_role("editor", parents=["viewer"])
        engine.assign_permission("editor", "edit:document", effect="ALLOW")

        engine.assign_user_role("alice", "editor")
        self.assertTrue(engine.evaluate("alice", "read:document"))
        self.assertTrue(engine.evaluate("alice", "edit:document"))

    def test_explicit_deny_overrides_allow(self):
        engine = RBACPolicyEngine()
        engine.add_role("employee")
        engine.assign_permission("employee", "access:financials", effect="ALLOW")

        # Contractor inherits employee permissions but has explicit DENY on financials
        engine.add_role("contractor", parents=["employee"])
        engine.assign_permission("contractor", "access:financials", effect="DENY")

        engine.assign_user_role("bob", "contractor")
        # Explicit DENY must override inherited ALLOW!
        self.assertFalse(engine.evaluate("bob", "access:financials"))
