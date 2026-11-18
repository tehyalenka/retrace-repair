class CyclicRoleInheritanceError(Exception):
    pass

class RBACPolicyEngine:
    def __init__(self):
        self.roles = {} # role -> list of parents
        self.permissions = {} # role -> dict(perm -> effect)
        self.user_roles = {} # user -> set(roles)

    def add_role(self, role, parents=None):
        # Buggy repo: does NOT check for cycles in inheritance graph!
        self.roles[role] = list(parents or [])
        if role not in self.permissions:
            self.permissions[role] = {}

    def assign_permission(self, role, permission, effect="ALLOW"):
        if role not in self.permissions:
            self.permissions[role] = {}
        self.permissions[role][permission] = effect

    def assign_user_role(self, user, role):
        if user not in self.user_roles:
            self.user_roles[user] = set()
        self.user_roles[user].add(role)

    def _get_all_roles(self, role):
        # Without cycle detection, this causes RecursionError on cycles
        res = {role}
        for parent in self.roles.get(role, []):
            res.update(self._get_all_roles(parent))
        return res

    def evaluate(self, user, permission):
        roles = set()
        for r in self.user_roles.get(user, []):
            roles.update(self._get_all_roles(r))

        has_allow = False
        has_deny = False

        for r in roles:
            eff = self.permissions.get(r, {}).get(permission)
            if eff == "ALLOW":
                has_allow = True
            elif eff == "DENY":
                has_deny = True

        # Security bug: ALLOW overrides DENY in buggy repo!
        if has_allow:
            return True
        if has_deny:
            return False
        return False
