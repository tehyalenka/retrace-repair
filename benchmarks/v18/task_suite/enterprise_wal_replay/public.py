import os
import tempfile
import unittest
from wal import WALEngine, CorruptedLogRecordError

class Public(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False)
        self.tmp.close()
        self.log_path = self.tmp.name

    def tearDown(self):
        if os.path.exists(self.log_path):
            os.remove(self.log_path)

    def test_uncommitted_tx_not_applied_on_recovery(self):
        engine = WALEngine(self.log_path)
        engine.begin_transaction("tx-1")
        engine.put("key1", "val1")
        self.assertTrue(engine.commit())

        engine.begin_transaction("tx-2")
        engine.put("key2", "val2")
        # tx-2 never committed!

        recovery_engine = WALEngine(self.log_path)
        recovery_engine.recover()
        self.assertEqual(recovery_engine.state.get("key1"), "val1")
        self.assertNotIn("key2", recovery_engine.state)

    def test_corrupted_crc_record_detected(self):
        engine = WALEngine(self.log_path)
        engine.begin_transaction("tx-1")
        engine.put("k", "v")
        engine.commit()

        # Corrupt the last byte of the file
        with open(self.log_path, "r+b") as f:
            f.seek(-1, os.SEEK_END)
            byte = f.read(1)
            f.seek(-1, os.SEEK_END)
            f.write(bytes([byte[0] ^ 0xFF]))

        recovery_engine = WALEngine(self.log_path)
        with self.assertRaises(CorruptedLogRecordError):
            recovery_engine.recover()
