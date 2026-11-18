import os
import struct
import zlib
import time

class CorruptedLogRecordError(Exception):
    pass

class WALEngine:
    """A Write-Ahead Log engine with binary record framing, CRC32 checksums, and recovery."""
    
    # Record format:
    # [4 bytes length][1 byte type][4 bytes crc32][payload bytes]
    # Type: 1 = TX_BEGIN, 2 = PUT, 3 = DELETE, 4 = TX_COMMIT, 5 = TX_ABORT, 6 = CHECKPOINT
    TYPE_BEGIN = 1
    TYPE_PUT = 2
    TYPE_DELETE = 3
    TYPE_COMMIT = 4
    TYPE_ABORT = 5
    TYPE_CHECKPOINT = 6

    def __init__(self, log_path):
        self.log_path = log_path
        self.state = {}
        self._current_tx = None
        self._uncommitted_ops = {}

    def begin_transaction(self, tx_id):
        self._current_tx = tx_id
        self._uncommitted_ops[tx_id] = []
        self._append_record(self.TYPE_BEGIN, tx_id.encode('utf-8'))

    def put(self, key, value):
        if not self._current_tx:
            raise RuntimeError("No active transaction")
        self._uncommitted_ops[self._current_tx].append(('PUT', key, value))
        payload = f"{self._current_tx}:{key}:{value}".encode('utf-8')
        self._append_record(self.TYPE_PUT, payload)

    def delete(self, key):
        if not self._current_tx:
            raise RuntimeError("No active transaction")
        self._uncommitted_ops[self._current_tx].append(('DELETE', key))
        payload = f"{self._current_tx}:{key}".encode('utf-8')
        self._append_record(self.TYPE_DELETE, payload)

    def commit(self):
        if not self._current_tx:
            raise RuntimeError("No active transaction")
        tx_id = self._current_tx
        self._append_record(self.TYPE_COMMIT, tx_id.encode('utf-8'))
        # Apply to state
        for op in self._uncommitted_ops[tx_id]:
            if op[0] == 'PUT':
                self.state[op[1]] = op[2]
            elif op[0] == 'DELETE':
                self.state.pop(op[1], None)
        del self._uncommitted_ops[tx_id]
        self._current_tx = None
        return True

    def abort(self):
        if not self._current_tx:
            raise RuntimeError("No active transaction")
        tx_id = self._current_tx
        self._append_record(self.TYPE_ABORT, tx_id.encode('utf-8'))
        del self._uncommitted_ops[tx_id]
        self._current_tx = None
        return True

    def checkpoint(self):
        # Writes checkpoint record containing current state keys
        self._append_record(self.TYPE_CHECKPOINT, b"CHECKPOINT")

    def _append_record(self, record_type, payload):
        # Bug in repo: DOES NOT compute or write CRC32 checksum properly, writes 0
        crc = 0
        length = len(payload)
        header = struct.pack(">IBI", length, record_type, crc)
        with open(self.log_path, "ab") as f:
            f.write(header + payload)

    def recover(self):
        # Buggy recover: Replays uncommitted and corrupted records, ignores CRC
        self.state = {}
        if not os.path.exists(self.log_path):
            return
        with open(self.log_path, "rb") as f:
            data = f.read()
        
        offset = 0
        while offset < len(data):
            if offset + 9 > len(data):
                break
            length, rtype, crc = struct.unpack(">IBI", data[offset:offset+9])
            offset += 9
            payload = data[offset:offset+length]
            offset += length
            
            # Bug: Applies operations directly without tracking transaction commit boundaries!
            if rtype == self.TYPE_PUT:
                parts = payload.decode('utf-8').split(':', 2)
                self.state[parts[1]] = parts[2]
            elif rtype == self.TYPE_DELETE:
                parts = payload.decode('utf-8').split(':', 1)
                self.state.pop(parts[1], None)
