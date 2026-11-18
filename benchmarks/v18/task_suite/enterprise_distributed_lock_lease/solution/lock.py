import time

class DistributedLockManager:
    def __init__(self):
        self.locks = {} # resource_id -> dict(owner, expires_at, fencing_token)
        self._global_fencing_token = 0

    def acquire(self, resource_id, owner_id, ttl_seconds, now=None):
        if not resource_id or not isinstance(resource_id, str):
            raise ValueError("resource_id must be non-empty string")
        if not owner_id or not isinstance(owner_id, str):
            raise ValueError("owner_id must be non-empty string")
        if not isinstance(ttl_seconds, (int, float)) or isinstance(ttl_seconds, bool) or ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive number")

        now = time.time() if now is None else now
        current = self.locks.get(resource_id)

        if current is not None:
            # Check if active and owned by someone else
            if current["expires_at"] > now and current["owner"] != owner_id:
                return False, None

        self._global_fencing_token += 1
        token = self._global_fencing_token
        self.locks[resource_id] = {
            "owner": owner_id,
            "expires_at": now + ttl_seconds,
            "fencing_token": token
        }
        return True, token

    def renew(self, resource_id, owner_id, ttl_seconds, now=None):
        if not resource_id or not owner_id:
            raise ValueError("resource_id and owner_id required")
        if not isinstance(ttl_seconds, (int, float)) or isinstance(ttl_seconds, bool) or ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive number")

        now = time.time() if now is None else now
        current = self.locks.get(resource_id)
        if current is None:
            return False

        # Only current non-expired owner can renew
        if current["owner"] != owner_id or current["expires_at"] <= now:
            return False

        current["expires_at"] = now + ttl_seconds
        return True

    def release(self, resource_id, owner_id, now=None):
        if not resource_id or not owner_id:
            raise ValueError("resource_id and owner_id required")

        now = time.time() if now is None else now
        current = self.locks.get(resource_id)
        if current is None:
            return False

        # Only current non-expired owner can release
        if current["owner"] != owner_id or current["expires_at"] <= now:
            return False

        del self.locks[resource_id]
        return True

    def get_fencing_token(self, resource_id):
        current = self.locks.get(resource_id)
        return current["fencing_token"] if current else None
