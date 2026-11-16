class Directory:
    def __init__(self, users):
        self.users = dict(users)
    def get(self, user_id):
        return self.users.get(user_id)
