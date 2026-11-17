import time
import sqlite3
from storage import connect

class CircuitBreakerOpenError(RuntimeError):
    pass

class CircuitBreaker:
    def __init__(self, db, failure_threshold=3, recovery_timeout=5.0):
        self.db = db
        self.failure_threshold = failure_threshold
        self.recovery_timeout = float(recovery_timeout)

    def state(self, service, now=None):
        return 'CLOSED'

    def failure_count(self, service):
        return 0

    def call(self, service, func, *args, now=None, **kwargs):
        # Buggy implementation: directly calls func without tracking state or tripping
        return func(*args, **kwargs)
