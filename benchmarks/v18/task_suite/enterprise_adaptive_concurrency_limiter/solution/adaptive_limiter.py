class AdaptiveConcurrencyLimiter:
    def __init__(self, initial_limit=10, min_limit=5, max_limit=50):
        if not isinstance(initial_limit, (int, float)) or initial_limit < 1:
            raise ValueError("initial_limit must be >= 1")
        if not isinstance(min_limit, (int, float)) or min_limit < 1:
            raise ValueError("min_limit must be >= 1")
        if not isinstance(max_limit, (int, float)) or max_limit < min_limit:
            raise ValueError("max_limit must be >= min_limit")

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
        if not isinstance(measured_rtt, (int, float)) or isinstance(measured_rtt, bool) or measured_rtt <= 0:
            raise ValueError("measured_rtt must be positive number")

        self.in_flight = max(0, self.in_flight - 1)
        if self.min_rtt is None:
            self.min_rtt = float(measured_rtt)
            return

        self.min_rtt = min(self.min_rtt, float(measured_rtt))

        # Vegas gradient formula
        gradient = self.min_rtt / float(measured_rtt)

        if float(measured_rtt) > self.min_rtt * 1.5:
            # Latency spike / queue build-up: throttle limit down
            new_limit = self.limit * gradient
        elif float(measured_rtt) <= self.min_rtt * 1.2:
            # Low latency: additive increase
            new_limit = self.limit + 1.0
        else:
            new_limit = self.limit

        self.limit = max(self.min_limit, min(self.max_limit, new_limit))
