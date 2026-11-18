import time

class SlidingWindowLogLimiter:
    def __init__(self, max_requests=5, window_seconds=60.0):
        if not isinstance(max_requests, int) or isinstance(max_requests, bool) or max_requests <= 0:
            raise ValueError("max_requests must be positive int")
        if not isinstance(window_seconds, (int, float)) or isinstance(window_seconds, bool) or window_seconds <= 0:
            raise ValueError("window_seconds must be positive number")

        self.max_requests = max_requests
        self.window_seconds = float(window_seconds)
        self.logs = {} # key -> list of float timestamps

    def allow(self, key, now=None):
        if not key or not isinstance(key, str):
            raise ValueError("key must be non-empty string")

        now = time.time() if now is None else now
        cutoff = now - self.window_seconds

        timestamps = self.logs.get(key, [])
        # Prune expired timestamps outside sliding window
        valid_timestamps = [t for t in timestamps if t > cutoff]

        if len(valid_timestamps) < self.max_requests:
            valid_timestamps.append(now)
            self.logs[key] = valid_timestamps
            return True, len(valid_timestamps)

        self.logs[key] = valid_timestamps
        return False, len(valid_timestamps)
