import time
import sqlite3
from storage import connect

class TokenBucketRateLimiter:
    def __init__(self, db):
        self.db = db

    def configure(self, key, capacity, refill_rate, now=None):
        now = time.time() if now is None else float(now)
        self.db.execute("INSERT INTO buckets VALUES (?, ?, ?, ?, ?)", (key, float(capacity), float(refill_rate), float(capacity), now))
        self.db.commit()

    def consume(self, key, tokens=1, now=None):
        # Buggy implementation: static counter without time-based refill
        row = self.db.execute("SELECT tokens FROM buckets WHERE key=?", (key,)).fetchone()
        if not row or row[0] < tokens:
            return False, 0.0, 1.0
        remaining = row[0] - tokens
        self.db.execute("UPDATE buckets SET tokens=? WHERE key=?", (remaining, key))
        self.db.commit()
        return True, remaining, 0.0
