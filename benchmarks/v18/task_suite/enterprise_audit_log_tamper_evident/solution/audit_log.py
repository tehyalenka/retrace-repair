import hashlib
import json
import time

class TamperEvidentAuditLog:
    GENESIS_HASH = "0" * 64

    def __init__(self):
        self.chain = []

    def _calc_hash(self, seq, timestamp, actor, action, details, prev_hash):
        content = json.dumps({
            "seq": seq,
            "timestamp": timestamp,
            "actor": actor,
            "action": action,
            "details": details,
            "prev_hash": prev_hash
        }, sort_keys=True)
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def append(self, actor, action, details, now=None):
        if not actor or not isinstance(actor, str):
            raise ValueError("actor must be non-empty string")
        if not action or not isinstance(action, str):
            raise ValueError("action must be non-empty string")
        if not isinstance(details, dict):
            raise ValueError("details must be a dictionary")

        now = time.time() if now is None else now
        seq = len(self.chain) + 1
        prev_hash = self.chain[-1]["hash"] if self.chain else self.GENESIS_HASH
        h = self._calc_hash(seq, now, actor, action, details, prev_hash)
        rec = {
            "seq": seq,
            "timestamp": now,
            "actor": actor,
            "action": action,
            "details": details,
            "prev_hash": prev_hash,
            "hash": h
        }
        self.chain.append(rec)
        return dict(rec)

    def verify_integrity(self):
        if not self.chain:
            return True, None, None

        for i, rec in enumerate(self.chain):
            expected_seq = i + 1
            if rec.get("seq") != expected_seq:
                return False, f"Sequence number mismatch: expected {expected_seq}, got {rec.get('seq')}", rec.get("seq")

            expected_prev = self.chain[i - 1]["hash"] if i > 0 else self.GENESIS_HASH
            if rec.get("prev_hash") != expected_prev:
                return False, f"Chain linkage broken at seq {rec.get('seq')}: prev_hash mismatch", rec.get("seq")

            expected_h = self._calc_hash(
                rec.get("seq"), rec.get("timestamp"), rec.get("actor"),
                rec.get("action"), rec.get("details"), rec.get("prev_hash")
            )
            if rec.get("hash") != expected_h:
                return False, f"Content tampering at seq {rec.get('seq')}: hash mismatch", rec.get("seq")

        return True, None, None
