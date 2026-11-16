class Gateway:
    def __init__(self, tokens, permissions):
        self.tokens = tokens
        self.permissions = permissions

    def allowed(self, token, resource):
        raise NotImplementedError
