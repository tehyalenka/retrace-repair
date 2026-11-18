import time

class DistributedLockManager:
    def __init__(self):
        self.locks = {} # resource_id -> dict(owner, expires_at, fencing_token)

    def acquire(self, resource_id, owner_id, ttl_seconds, now=None):
        now = time.time() if now is None else now
        # Buggy repo: Static fencing token = 1, and doesn't check expiration properly
        if resource_id in self.locks:
            current = self.locks[resource_id]
            if current["owner"] != owner_id:
                return False, None
        
        self.locks[resource_id] = {
            "owner": owner_id,
            "expires_at": now + ttl_seconds,
            "fencing_token": 1 # Bug: fixed token
        }
        return True, 1

    def renew(self, resource_id, owner_id, ttl_seconds, now=None):
        now = time.time() if now is None else now
        # Bug: Does not check if the lease already expired!
        if resource_id in self.locks:
            self.locks[resource_id]["expires_at"] = now + ttl_seconds
            return True
        return False

    def release(self, resource_id, owner_id, now=None):
        # Bug: Stale owner can release anytime
        if resource_id in self.locks:
            del self.locks[resource_id]
            return True
        return False
