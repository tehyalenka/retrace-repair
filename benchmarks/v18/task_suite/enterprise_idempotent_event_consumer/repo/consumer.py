import hashlib
import json
import time

class ConflictingPayloadError(ValueError):
    pass

class IdempotentConsumer:
    def __init__(self, window_seconds=300.0):
        self.window_seconds = window_seconds
        self.processed = {} # event_id -> dict

    def _hash_payload(self, payload):
        raw = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()

    def process(self, event_id, payload, handler, now=None):
        now = time.time() if now is None else now
        
        # Buggy repo:
        # 1. Does not check if the payload matches! Returns cached result blindly even if payload differs.
        # 2. Inserts into self.processed BEFORE calling handler!
        if event_id in self.processed:
            # Bug: ignores payload conflict check!
            return self.processed[event_id]["result"]

        # Bug: marks as processed before handler runs
        self.processed[event_id] = {
            "payload_hash": self._hash_payload(payload),
            "result": None,
            "timestamp": now
        }
        res = handler(payload)
        self.processed[event_id]["result"] = res
        return res
