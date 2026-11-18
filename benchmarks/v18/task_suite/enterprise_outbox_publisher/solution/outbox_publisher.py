import time
import json
from storage import connect

class OutboxPublisher:
    def __init__(self, db):
        self.db = db

    def insert_event(self, agg_type, agg_id, payload, now=None):
        if not agg_type or not agg_id:
            raise ValueError("agg_type and agg_id required")
        now = time.time() if now is None else now
        cur = self.db.execute(
            "INSERT INTO outbox (aggregate_type, aggregate_id, payload, status, created_at) VALUES (?, ?, ?, 'PENDING', ?)",
            (agg_type, agg_id, json.dumps(payload), now)
        )
        self.db.commit()
        return cur.lastrowid

    def poll_and_publish(self, broker, batch_size=10, max_attempts=3, now=None):
        if not hasattr(broker, "publish") or not callable(broker.publish):
            raise ValueError("broker must have callable publish method")
        if not isinstance(batch_size, int) or isinstance(batch_size, bool) or batch_size <= 0:
            raise ValueError("batch_size must be positive integer")
        if not isinstance(max_attempts, int) or isinstance(max_attempts, bool) or max_attempts <= 0:
            raise ValueError("max_attempts must be positive integer")

        now = time.time() if now is None else now
        rows = self.db.execute(
            "SELECT id, aggregate_type, aggregate_id, payload, attempts FROM outbox WHERE status='PENDING' ORDER BY id ASC LIMIT ?",
            (batch_size,)
        ).fetchall()

        published_count = 0
        for row in rows:
            rec_id, agg_type, agg_id, payload_str, attempts = row
            payload = json.loads(payload_str)
            
            try:
                broker.publish(agg_type, payload)
                self.db.execute("UPDATE outbox SET status='PUBLISHED', published_at=? WHERE id=?", (now, rec_id))
                self.db.commit()
                published_count += 1
            except Exception:
                new_attempts = attempts + 1
                new_status = 'FAILED' if new_attempts >= max_attempts else 'PENDING'
                self.db.execute("UPDATE outbox SET attempts=?, status=? WHERE id=?", (new_attempts, new_status, rec_id))
                self.db.commit()

        return published_count
