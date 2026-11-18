class CyclicRoleInheritanceError(Exception):
    pass

class RBACPolicyEngine:
    def __init__(self):
        self.roles = {} # role -> list of parents
        self.permissions = {} # role -> dict(perm -> effect)
        self.user_roles = {} # user -> set(roles)

    def _check_cycle(self, role, parents):
        # Check if role is reachable from any parent
        visited = set()
        stack = list(parents)
        while stack:
            curr = stack.pop()
            if curr == role:
                return True
            if curr not in visited:
                visited.add(curr)
                stack.extend(self.roles.get(curr, []))
        return False

    def add_role(self, role, parents=None):
        if not role or not isinstance(role, str):
            raise ValueError("role must be non-empty string")
        parents = list(parents or [])
        for p in parents:
            if not isinstance(p, str):
                raise ValueError("parent role must be string")

        if self._check_cycle(role, parents):
            raise CyclicRoleInheritanceError(f"Cycle detected adding role '{role}' with parents {parents}")

        self.roles[role] = parents
        if role not in self.permissions:
            self.permissions[role] = {}

    def assign_permission(self, role, permission, effect="ALLOW"):
        if not role or not permission:
            raise ValueError("role and permission required")
        if effect not in ("ALLOW", "DENY"):
            raise ValueError("effect must be 'ALLOW' or 'DENY'")
        if role not in self.permissions:
            self.permissions[role] = {}
        self.permissions[role][permission] = effect

    def assign_user_role(self, user, role):
        if not user or not role:
            raise ValueError("user and role required")
        if role not in self.roles:
            raise ValueError(f"Role '{role}' does not exist")
        if user not in self.user_roles:
            self.user_roles[user] = set()
        self.user_roles[user].add(role)

    def _get_all_roles(self, role):
        res = set()
        stack = [role]
        while stack:
            curr = stack.pop()
            if curr not in res:
                res.add(curr)
                stack.extend(self.roles.get(curr, []))
        return res

    def evaluate(self, user, permission):
        if not user or not permission:
            return False

        roles = set()
        for r in self.user_roles.get(user, []):
            roles.update(self._get_all_roles(r))

        has_allow = False
        has_deny = False

        for r in roles:
            eff = self.permissions.get(r, {}).get(permission)
            if eff == "DENY":
                has_deny = True
                break # Explicit deny immediately vetoes
            elif eff == "ALLOW":
                has_allow = True

        if has_deny:
            return False
        if has_allow:
            return True
        return False # Deny by default
