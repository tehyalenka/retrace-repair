import time
import json
from storage import connect

class OutboxPublisher:
    def __init__(self, db):
        self.db = db

    def insert_event(self, agg_type, agg_id, payload, now=None):
        now = time.time() if now is None else now
        cur = self.db.execute(
            "INSERT INTO outbox (aggregate_type, aggregate_id, payload, status, created_at) VALUES (?, ?, ?, 'PENDING', ?)",
            (agg_type, agg_id, json.dumps(payload), now)
        )
        self.db.commit()
        return cur.lastrowid

    def poll_and_publish(self, broker, batch_size=10, max_attempts=3, now=None):
        now = time.time() if now is None else now
        rows = self.db.execute(
            "SELECT id, aggregate_type, aggregate_id, payload, attempts FROM outbox WHERE status='PENDING' ORDER BY id ASC LIMIT ?",
            (batch_size,)
        ).fetchall()

        published_count = 0
        for row in rows:
            rec_id, agg_type, agg_id, payload_str, attempts = row
            payload = json.loads(payload_str)
            
            # Buggy repo: marks as PUBLISHED BEFORE sending to broker!
            # If broker fails, message is lost forever!
            self.db.execute("UPDATE outbox SET status='PUBLISHED', published_at=? WHERE id=?", (now, rec_id))
            self.db.commit()

            broker.publish(agg_type, payload)
            published_count += 1

        return published_count
