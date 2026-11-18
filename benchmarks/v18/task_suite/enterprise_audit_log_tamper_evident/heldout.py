import unittest
from audit_log import TamperEvidentAuditLog

class Heldout(unittest.TestCase):
    def test_content_tampering_detected(self):
        log = TamperEvidentAuditLog()
        log.append("alice", "TRANSFER", {"amount": 100}, now=100.0)
        log.append("bob", "TRANSFER", {"amount": 200}, now=101.0)

        # Attacker modifies details of record 1 (amount 100 -> 999999)
        log.chain[0]["details"]["amount"] = 999999

        is_valid, err, seq = log.verify_integrity()
        self.assertFalse(is_valid)
        self.assertEqual(seq, 1)
        self.assertIn("Content tampering", err)

    def test_sequence_discontinuity_detected(self):
        log = TamperEvidentAuditLog()
        log.append("u1", "A", {}, now=1.0)
        log.append("u2", "B", {}, now=2.0)
        # Corrupt sequence number of record 2
        log.chain[1]["seq"] = 5

        is_valid, err, seq = log.verify_integrity()
        self.assertFalse(is_valid)
        self.assertEqual(seq, 5)

    def test_empty_log_is_valid(self):
        log = TamperEvidentAuditLog()
        is_valid, _, _ = log.verify_integrity()
        self.assertTrue(is_valid)

    def test_invalid_parameters_raise_value_error(self):
        log = TamperEvidentAuditLog()
        with self.assertRaises(ValueError):
            log.append("", "ACTION", {})
        with self.assertRaises(ValueError):
            log.append("u", "", {})
        with self.assertRaises(ValueError):
            log.append("u", "ACTION", "not a dict")
