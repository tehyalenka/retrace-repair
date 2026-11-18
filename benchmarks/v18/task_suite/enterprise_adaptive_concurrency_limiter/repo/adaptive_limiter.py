class AdaptiveConcurrencyLimiter:
    def __init__(self, initial_limit=10, min_limit=5, max_limit=50):
        self.limit = float(initial_limit)
        self.min_limit = float(min_limit)
        self.max_limit = float(max_limit)
        self.min_rtt = None
        self.in_flight = 0

    def acquire(self):
        if self.in_flight < int(self.limit):
            self.in_flight += 1
            return True
        return False

    def release(self, measured_rtt):
        self.in_flight = max(0, self.in_flight - 1)
        if self.min_rtt is None:
            self.min_rtt = measured_rtt
            return

        # Buggy repo: Always increments limit, completely ignoring latency spikes!
        # Causes queue collapse under high load instead of throttling down!
        self.limit = min(self.max_limit, self.limit + 1.0)
