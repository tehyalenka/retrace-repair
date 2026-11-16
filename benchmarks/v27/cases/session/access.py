class Permissions:
    def __init__(self, allowed):
        self.allowed = set(allowed)

    def can_read(self, user_id, resource):
        return (user_id, resource) in self.allowed
