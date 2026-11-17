import time
import sqlite3
from storage import connect

class TokenBucketRateLimiter:
    def __init__(self, db):
        self.db = db

    def configure(self, key, capacity, refill_rate, now=None):
        if not key or not isinstance(key, str):
            raise ValueError("key required")
        if not isinstance(capacity, (int, float)) or isinstance(capacity, bool) or capacity <= 0:
            raise ValueError("capacity must be positive number")
        if not isinstance(refill_rate, (int, float)) or isinstance(refill_rate, bool) or refill_rate <= 0:
            raise ValueError("refill_rate must be positive number")

        now = time.time() if now is None else float(now)
        self.db.execute(
            "INSERT INTO buckets VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET capacity=excluded.capacity, refill_rate=excluded.refill_rate",
            (key, float(capacity), float(refill_rate), float(capacity), now)
        )
        self.db.commit()

    def consume(self, key, tokens=1, now=None):
        if not isinstance(tokens, int) or isinstance(tokens, bool) or tokens <= 0:
            raise ValueError("tokens must be positive integer")
        now = time.time() if now is None else float(now)

        try:
            self.db.execute("BEGIN IMMEDIATE")
            row = self.db.execute("SELECT capacity, refill_rate, tokens, last_updated FROM buckets WHERE key=?", (key,)).fetchone()
            if not row:
                self.db.rollback()
                raise ValueError("Unconfigured bucket")

            cap, rate, cur_tokens, last_up = row
            elapsed = max(0.0, now - last_up)
            refilled = min(cap, cur_tokens + (elapsed * rate))

            if refilled >= tokens:
                remaining = refilled - tokens
                self.db.execute("UPDATE buckets SET tokens=?, last_updated=? WHERE key=?", (remaining, now, key))
                self.db.commit()
                return True, round(remaining, 4), 0.0
            else:
                deficit = tokens - refilled
                wait_time = deficit / rate
                # Update refilled tokens up to now without deducting
                self.db.execute("UPDATE buckets SET tokens=?, last_updated=? WHERE key=?", (refilled, now, key))
                self.db.commit()
                return False, round(refilled, 4), round(wait_time, 4)
        except Exception:
            self.db.rollback()
            raise
