import time
import sqlite3
from storage import connect

class CircuitBreakerOpenError(RuntimeError):
    """Raised when call is rejected because circuit is open."""
    pass

class CircuitBreaker:
    def __init__(self, db, failure_threshold=3, recovery_timeout=5.0):
        if not isinstance(failure_threshold, int) or isinstance(failure_threshold, bool) or failure_threshold <= 0:
            raise ValueError("failure_threshold must be positive int")
        if not isinstance(recovery_timeout, (int, float)) or isinstance(recovery_timeout, bool) or recovery_timeout <= 0:
            raise ValueError("recovery_timeout must be positive number")
        self.db = db
        self.failure_threshold = failure_threshold
        self.recovery_timeout = float(recovery_timeout)

    def _get_or_create(self, service):
        row = self.db.execute("SELECT state, failure_count, last_failure_time, tripped_at FROM circuit_states WHERE service=?", (service,)).fetchone()
        if not row:
            self.db.execute("INSERT INTO circuit_states VALUES (?, 'CLOSED', 0, NULL, NULL)", (service,))
            self.db.commit()
            return 'CLOSED', 0, None, None
        return row

    def state(self, service, now=None):
        if not service:
            raise ValueError("service required")
        now = time.time() if now is None else now
        current_state, fails, last_fail, tripped_at = self._get_or_create(service)
        if current_state == 'OPEN' and tripped_at is not None:
            if now - tripped_at >= self.recovery_timeout:
                self.db.execute("UPDATE circuit_states SET state='HALF_OPEN' WHERE service=?", (service,))
                self.db.commit()
                return 'HALF_OPEN'
        return current_state

    def failure_count(self, service):
        return self._get_or_create(service)[1]

    def call(self, service, func, *args, now=None, **kwargs):
        if not service:
            raise ValueError("service required")
        now = time.time() if now is None else now
        current_state = self.state(service, now=now)

        if current_state == 'OPEN':
            raise CircuitBreakerOpenError(f"Circuit for {service} is OPEN")

        try:
            result = func(*args, **kwargs)
            # Success in CLOSED or HALF_OPEN resets circuit
            self.db.execute("UPDATE circuit_states SET state='CLOSED', failure_count=0, tripped_at=NULL WHERE service=?", (service,))
            self.db.commit()
            return result
        except Exception:
            _, fails, _, _ = self._get_or_create(service)
            new_fails = fails + 1
            if current_state == 'HALF_OPEN' or new_fails >= self.failure_threshold:
                self.db.execute("UPDATE circuit_states SET state='OPEN', failure_count=?, last_failure_time=?, tripped_at=? WHERE service=?",
                                (new_fails, now, now, service))
            else:
                self.db.execute("UPDATE circuit_states SET failure_count=?, last_failure_time=? WHERE service=?",
                                (new_fails, now, service))
            self.db.commit()
            raise
