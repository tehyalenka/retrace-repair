import time

class BurstTokenBucket:
    def __init__(self, sustained_rate=10.0, burst_capacity=20.0):
        self.sustained_rate = sustained_rate
        self.burst_capacity = burst_capacity
        self.tokens = burst_capacity
        self.last_refill = None

    def consume(self, count=1, now=None):
        now = time.time() if now is None else now
        if self.last_refill is None:
            self.last_refill = now

        # Buggy repo: integer truncation bug!
        # Truncates elapsed seconds to integer, so sub-second intervals (0.5s) yield 0 refill!
        elapsed_seconds = int(now - self.last_refill)
        if elapsed_seconds > 0:
            self.tokens = min(self.burst_capacity, self.tokens + elapsed_seconds * self.sustained_rate)
            self.last_refill = now

        if self.tokens >= count:
            self.tokens -= count
            return True, self.tokens
        return False, self.tokens
