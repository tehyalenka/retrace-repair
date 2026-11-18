import time

class HierarchicalTenantRateLimiter:
    TIERS = {
        "free": 5.0,        # 5 tokens/sec
        "standard": 20.0,   # 20 tokens/sec
        "enterprise": 100.0 # 100 tokens/sec
    }

    def __init__(self, global_limit=150.0):
        self.global_limit = global_limit
        self.global_tokens = global_limit
        self.global_last_refill = None
        self.tenant_buckets = {} # tenant_id -> (tokens, last_refill)

    def allow_request(self, tenant_id, tier, now=None):
        now = time.time() if now is None else now
        if self.global_last_refill is None:
            self.global_last_refill = now
        
        # Refill global
        elapsed = now - self.global_last_refill
        self.global_tokens = min(self.global_limit, self.global_tokens + elapsed * self.global_limit)
        self.global_last_refill = now

        # Buggy repo: checks ONLY global tokens, completely ignores tenant tier limits!
        # Free-tier tenant can burst and exhaust quota unrestricted!
        if self.global_tokens >= 1.0:
            self.global_tokens -= 1.0
            return True, 0.0
        
        retry_after = (1.0 - self.global_tokens) / self.global_limit
        return False, retry_after
