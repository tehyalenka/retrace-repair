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
        # Buggy repo: checks ONLY internal record hash, but DOES NOT check chain linkage (prev_hash)!
        # If a record is inserted or deleted, it does NOT detect the broken hash chain!
        for rec in self.chain:
            expected_h = self._calc_hash(
                rec["seq"], rec["timestamp"], rec["actor"], rec["action"], rec["details"], rec["prev_hash"]
            )
            if rec["hash"] != expected_h:
                return False, f"Hash mismatch at seq {rec['seq']}", rec["seq"]
        return True, None, None
