import unittest
from storage import connect
from outbox_publisher import OutboxPublisher

class MockBroker:
    def __init__(self, fail_topics=None):
        self.published = []
        self.fail_topics = set(fail_topics or [])

    def publish(self, topic, payload):
        if topic in self.fail_topics:
            raise ConnectionError("broker connection refused")
        self.published.append((topic, payload))

class Public(unittest.TestCase):
    def test_successful_outbox_publish(self):
        db = connect()
        pub = OutboxPublisher(db)
        broker = MockBroker()

        rec_id = pub.insert_event("orders", "ord-1", {"amount": 100})
        count = pub.poll_and_publish(broker)

        self.assertEqual(count, 1)
        self.assertEqual(len(broker.published), 1)
        row = db.execute("SELECT status, published_at FROM outbox WHERE id=?", (rec_id,)).fetchone()
        self.assertEqual(row[0], "PUBLISHED")
        self.assertIsNotNone(row[1])

    def test_broker_failure_keeps_record_pending_for_retry(self):
        db = connect()
        pub = OutboxPublisher(db)
        broker = MockBroker(fail_topics={"payments"})

        rec_id = pub.insert_event("payments", "pay-1", {"amount": 50})
        count = pub.poll_and_publish(broker, max_attempts=3)

        self.assertEqual(count, 0)
        # Record must NOT be marked PUBLISHED if broker failed!
        row = db.execute("SELECT status, attempts FROM outbox WHERE id=?", (rec_id,)).fetchone()
        self.assertEqual(row[0], "PENDING")
        self.assertEqual(row[1], 1)
