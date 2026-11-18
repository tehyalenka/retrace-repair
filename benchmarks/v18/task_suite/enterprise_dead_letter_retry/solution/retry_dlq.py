class RetryableError(Exception):
    pass

class NonRetryableError(Exception):
    pass

class MockDLQSink:
    def __init__(self):
        self.records = []

    def send(self, payload, error, attempts):
        self.records.append({
            "payload": payload,
            "error": str(error),
            "attempts": attempts
        })

class RetryDispatcher:
    def __init__(self, max_attempts=3, base_delay=0.1, max_delay=1.0):
        if not isinstance(max_attempts, int) or isinstance(max_attempts, bool) or max_attempts <= 0:
            raise ValueError("max_attempts must be positive integer")
        if not isinstance(base_delay, (int, float)) or isinstance(base_delay, bool) or base_delay <= 0:
            raise ValueError("base_delay must be positive number")
        if not isinstance(max_delay, (int, float)) or isinstance(max_delay, bool) or max_delay < base_delay:
            raise ValueError("max_delay must be >= base_delay")

        self.max_attempts = max_attempts
        self.base_delay = float(base_delay)
        self.max_delay = float(max_delay)

    def calculate_backoff(self, attempt):
        if attempt <= 0:
            return 0.0
        delay = self.base_delay * (2 ** (attempt - 1))
        return min(delay, self.max_delay)

    def execute(self, func, payload, dlq_sink):
        if not callable(func):
            raise ValueError("func must be callable")
        if not hasattr(dlq_sink, "send") or not callable(dlq_sink.send):
            raise ValueError("dlq_sink must have a callable send method")

        attempts = 0
        while attempts < self.max_attempts:
            attempts += 1
            try:
                return func(payload)
            except NonRetryableError as fatal:
                dlq_sink.send(payload, fatal, attempts)
                raise
            except Exception as transient:
                if attempts >= self.max_attempts:
                    dlq_sink.send(payload, transient, attempts)
                    raise
