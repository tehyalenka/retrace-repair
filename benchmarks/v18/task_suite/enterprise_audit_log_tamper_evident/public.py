import unittest
from audit_log import TamperEvidentAuditLog

class Public(unittest.TestCase):
    def test_valid_chain_verifies(self):
        log = TamperEvidentAuditLog()
        log.append("alice", "LOGIN", {"ip": "1.1.1.1"}, now=100.0)
        log.append("alice", "TRANSFER", {"amount": 500}, now=101.0)
        is_valid, err, seq = log.verify_integrity()
        self.assertTrue(is_valid)
        self.assertIsNone(err)

    def test_chain_linkage_tampering_detected(self):
        log = TamperEvidentAuditLog()
        log.append("alice", "LOGIN", {"ip": "1.1.1.1"}, now=100.0)
        log.append("bob", "ACCESS", {"resource": "docs"}, now=101.0)
        log.append("alice", "TRANSFER", {"amount": 500}, now=102.0)

        # Attacker deletes the middle record (seq 2) to hide Bob's access
        del log.chain[1]
        # Re-number sequence so individual records look valid
        log.chain[1]["seq"] = 2

        # Integrity verification MUST fail because record 2's prev_hash links to deleted record's hash!
        is_valid, err, seq = log.verify_integrity()
        self.assertFalse(is_valid)
        self.assertIsNotNone(err)
        self.assertIn("Chain linkage broken", err)
