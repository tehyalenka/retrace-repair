import time

class HierarchicalTenantRateLimiter:
    TIERS = {
        "free": 5.0,
        "standard": 20.0,
        "enterprise": 100.0
    }

    def __init__(self, global_limit=150.0):
        if not isinstance(global_limit, (int, float)) or isinstance(global_limit, bool) or global_limit <= 0:
            raise ValueError("global_limit must be positive number")
        self.global_limit = float(global_limit)
        self.global_tokens = self.global_limit
        self.global_last_refill = None
        self.tenant_buckets = {}

    def allow_request(self, tenant_id, tier, now=None):
        if not tenant_id or not isinstance(tenant_id, str):
            raise ValueError("tenant_id must be non-empty string")
        if tier not in self.TIERS:
            raise ValueError(f"Unknown tier: {tier}")

        now = time.time() if now is None else now
        if self.global_last_refill is None:
            self.global_last_refill = now

        # Refill global
        elapsed_global = max(0.0, now - self.global_last_refill)
        self.global_tokens = min(self.global_limit, self.global_tokens + elapsed_global * self.global_limit)
        self.global_last_refill = now

        # Refill tenant
        tenant_limit = self.TIERS[tier]
        if tenant_id not in self.tenant_buckets:
            tokens = tenant_limit
            last_refill = now
        else:
            tokens, last_refill = self.tenant_buckets[tenant_id]
            elapsed_tenant = max(0.0, now - last_refill)
            tokens = min(tenant_limit, tokens + elapsed_tenant * tenant_limit)
            last_refill = now

        # Check tenant quota first
        if tokens < 1.0:
            retry_after = (1.0 - tokens) / tenant_limit
            self.tenant_buckets[tenant_id] = (tokens, last_refill)
            return False, retry_after

        # Check global quota
        if self.global_tokens < 1.0:
            retry_after = (1.0 - self.global_tokens) / self.global_limit
            self.tenant_buckets[tenant_id] = (tokens, last_refill)
            return False, retry_after

        # Consume from both
        tokens -= 1.0
        self.global_tokens -= 1.0
        self.tenant_buckets[tenant_id] = (tokens, last_refill)
        return True, 0.0
