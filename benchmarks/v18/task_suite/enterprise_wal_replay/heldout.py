import os
import tempfile
import unittest
from wal import WALEngine, CorruptedLogRecordError

class Heldout(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False)
        self.tmp.close()
        self.log_path = self.tmp.name

    def tearDown(self):
        if os.path.exists(self.log_path):
            os.remove(self.log_path)

    def test_aborted_transaction_discarded(self):
        e = WALEngine(self.log_path)
        e.begin_transaction("t1")
        e.put("k1", "v1")
        e.abort()

        rec = WALEngine(self.log_path)
        rec.recover()
        self.assertNotIn("k1", rec.state)

    def test_checkpoint_and_subsequent_replay(self):
        e = WALEngine(self.log_path)
        e.begin_transaction("t1")
        e.put("k1", "v1")
        e.commit()
        e.checkpoint()

        e.begin_transaction("t2")
        e.put("k2", "v2")
        e.delete("k1")
        e.commit()

        rec = WALEngine(self.log_path)
        rec.recover()
        self.assertNotIn("k1", rec.state)
        self.assertEqual(rec.state.get("k2"), "v2")

    def test_interleaved_transactions_isolation(self):
        e = WALEngine(self.log_path)
        e.begin_transaction("t1")
        e.put("a", "1")
        # Start t2
        e.begin_transaction("t2")
        e.put("b", "2")
        e.commit() # t2 committed
        # t1 still uncommitted

        rec = WALEngine(self.log_path)
        rec.recover()
        self.assertNotIn("a", rec.state)
        self.assertEqual(rec.state.get("b"), "2")

    def test_truncated_header_raises_corruption(self):
        e = WALEngine(self.log_path)
        e.begin_transaction("t1")
        e.put("k", "v")
        e.commit()

        # Append 3 extra partial bytes to simulate write crash
        with open(self.log_path, "ab") as f:
            f.write(b"\x00\x01\x02")

        rec = WALEngine(self.log_path)
        with self.assertRaises(CorruptedLogRecordError):
            rec.recover()

    def test_invalid_types_raise_value_error(self):
        e = WALEngine(self.log_path)
        with self.assertRaises(ValueError):
            e.begin_transaction("")
        e.begin_transaction("tx-valid")
        with self.assertRaises(ValueError):
            e.put(123, "val")
        with self.assertRaises(ValueError):
            e.delete(456)
