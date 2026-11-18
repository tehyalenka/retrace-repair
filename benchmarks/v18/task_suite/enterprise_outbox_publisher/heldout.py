import unittest
from storage import connect
from outbox_publisher import OutboxPublisher

class FlakyBroker:
    def __init__(self):
        self.published = []

    def publish(self, topic, payload):
        if payload.get("bad"):
            raise ValueError("bad message schema")
        self.published.append((topic, payload))

class Heldout(unittest.TestCase):
    def test_exhausted_attempts_transitions_to_failed(self):
        db = connect()
        pub = OutboxPublisher(db)
        broker = FlakyBroker()

        rec_id = pub.insert_event("events", "ev-1", {"bad": True})
        # Attempt 1
        pub.poll_and_publish(broker, max_attempts=2)
        r1 = db.execute("SELECT status, attempts FROM outbox WHERE id=?", (rec_id,)).fetchone()
        self.assertEqual(r1[0], "PENDING")
        self.assertEqual(r1[1], 1)

        # Attempt 2 -> transitions to FAILED
        pub.poll_and_publish(broker, max_attempts=2)
        r2 = db.execute("SELECT status, attempts FROM outbox WHERE id=?", (rec_id,)).fetchone()
        self.assertEqual(r2[0], "FAILED")
        self.assertEqual(r2[1], 2)

    def test_batching_limit(self):
        db = connect()
        pub = OutboxPublisher(db)
        broker = FlakyBroker()

        for i in range(5):
            pub.insert_event("topic", f"id-{i}", {"i": i})

        # Process batch of 2
        count = pub.poll_and_publish(broker, batch_size=2)
        self.assertEqual(count, 2)
        remaining = db.execute("SELECT count(*) FROM outbox WHERE status='PENDING'").fetchone()[0]
        self.assertEqual(remaining, 3)

    def test_invalid_parameters_raise_value_error(self):
        db = connect()
        pub = OutboxPublisher(db)
        with self.assertRaises(ValueError):
            pub.insert_event("", "1", {})
        with self.assertRaises(ValueError):
            pub.poll_and_publish("not a broker")
        with self.assertRaises(ValueError):
            pub.poll_and_publish(FlakyBroker(), batch_size=0)
