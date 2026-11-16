class TokenStore:
    def __init__(self, clock):
        self.clock = clock
        self.tokens = {}

    def issue(self, token, user_id, ttl):
        raise NotImplementedError

    def resolve(self, token):
        raise NotImplementedError

    def revoke(self, token):
        raise NotImplementedError
