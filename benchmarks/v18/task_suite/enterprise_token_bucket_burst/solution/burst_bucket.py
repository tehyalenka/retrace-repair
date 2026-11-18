import time

class BurstTokenBucket:
    def __init__(self, sustained_rate=10.0, burst_capacity=20.0):
        if not isinstance(sustained_rate, (int, float)) or isinstance(sustained_rate, bool) or sustained_rate <= 0:
            raise ValueError("sustained_rate must be positive number")
        if not isinstance(burst_capacity, (int, float)) or isinstance(burst_capacity, bool) or burst_capacity <= 0:
            raise ValueError("burst_capacity must be positive number")

        self.sustained_rate = float(sustained_rate)
        self.burst_capacity = float(burst_capacity)
        self.tokens = self.burst_capacity
        self.last_refill = None

    def consume(self, count=1, now=None):
        if not isinstance(count, (int, float)) or isinstance(count, bool) or count <= 0:
            raise ValueError("count must be positive number")

        now = time.time() if now is None else now
        if self.last_refill is None:
            self.last_refill = now

        elapsed = max(0.0, now - self.last_refill)
        self.tokens = min(self.burst_capacity, self.tokens + elapsed * self.sustained_rate)
        self.last_refill = now

        if self.tokens >= count:
            self.tokens -= count
            return True, self.tokens
        return False, self.tokens
