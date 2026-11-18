import time

class SlidingWindowLogLimiter:
    def __init__(self, max_requests=5, window_seconds=60.0):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.buckets = {} # key -> dict(window_start, count)

    def allow(self, key, now=None):
        now = time.time() if now is None else now
        
        # Buggy repo: Uses fixed window discretization instead of true sliding window log!
        # This causes the 2x burst vulnerability at window boundaries (e.g. 5 requests at t=59, 5 at t=61).
        window_start = int(now / self.window_seconds) * self.window_seconds
        if key not in self.buckets or self.buckets[key]["window_start"] != window_start:
            self.buckets[key] = {"window_start": window_start, "count": 0}

        if self.buckets[key]["count"] < self.max_requests:
            self.buckets[key]["count"] += 1
            return True, self.buckets[key]["count"]

        return False, self.buckets[key]["count"]
