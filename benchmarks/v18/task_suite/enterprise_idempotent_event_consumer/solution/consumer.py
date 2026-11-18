import hashlib
import json
import time

class ConflictingPayloadError(ValueError):
    pass

class IdempotentConsumer:
    def __init__(self, window_seconds=300.0):
        if not isinstance(window_seconds, (int, float)) or isinstance(window_seconds, bool) or window_seconds <= 0:
            raise ValueError("window_seconds must be positive number")
        self.window_seconds = float(window_seconds)
        self.processed = {} # event_id -> dict

    def _hash_payload(self, payload):
        raw = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()

    def _evict_expired(self, now):
        cutoff = now - self.window_seconds
        expired = [eid for eid, data in self.processed.items() if data["timestamp"] < cutoff]
        for eid in expired:
            del self.processed[eid]

    def process(self, event_id, payload, handler, now=None):
        if not event_id or not isinstance(event_id, str):
            raise ValueError("event_id must be non-empty string")
        if not callable(handler):
            raise ValueError("handler must be callable")

        now = time.time() if now is None else now
        self._evict_expired(now)

        current_hash = self._hash_payload(payload)
        if event_id in self.processed:
            stored = self.processed[event_id]
            if stored["payload_hash"] != current_hash:
                raise ConflictingPayloadError(
                    f"Conflicting payload for event_id '{event_id}': original hash {stored['payload_hash']} != {current_hash}"
                )
            return stored["result"]

        # Execute handler; do NOT mark as processed if handler fails
        res = handler(payload)

        self.processed[event_id] = {
            "payload_hash": current_hash,
            "result": res,
            "timestamp": now
        }
        return res
