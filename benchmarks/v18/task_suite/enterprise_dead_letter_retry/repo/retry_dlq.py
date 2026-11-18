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
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay

    def calculate_backoff(self, attempt):
        # Exponential backoff clamped to max_delay
        delay = self.base_delay * (2 ** (attempt - 1))
        return min(delay, self.max_delay)

    def execute(self, func, payload, dlq_sink):
        # Buggy repo:
        # Retries ALL exceptions (including NonRetryableError), and does NOT send to DLQ on failure!
        attempts = 0
        last_err = None
        while attempts < self.max_attempts:
            attempts += 1
            try:
                return func(payload)
            except Exception as e:
                last_err = e
                # Bug: No DLQ routing, no error classification
        raise last_err
