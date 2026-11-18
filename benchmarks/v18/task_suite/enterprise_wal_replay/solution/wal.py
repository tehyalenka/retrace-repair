import os
import struct
import zlib
import json

class CorruptedLogRecordError(Exception):
    pass

class WALEngine:
    """A Write-Ahead Log engine with binary record framing, CRC32 checksums, and recovery."""
    
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
        if not tx_id or not isinstance(tx_id, str):
            raise ValueError("Invalid tx_id")
        self._current_tx = tx_id
        self._uncommitted_ops[tx_id] = []
        self._append_record(self.TYPE_BEGIN, tx_id.encode('utf-8'))

    def put(self, key, value):
        if not self._current_tx:
            raise RuntimeError("No active transaction")
        if not isinstance(key, str) or not isinstance(value, str):
            raise ValueError("Key and value must be strings")
        self._uncommitted_ops[self._current_tx].append(('PUT', key, value))
        payload = f"{self._current_tx}:{key}:{value}".encode('utf-8')
        self._append_record(self.TYPE_PUT, payload)

    def delete(self, key):
        if not self._current_tx:
            raise RuntimeError("No active transaction")
        if not isinstance(key, str):
            raise ValueError("Key must be string")
        self._uncommitted_ops[self._current_tx].append(('DELETE', key))
        payload = f"{self._current_tx}:{key}".encode('utf-8')
        self._append_record(self.TYPE_DELETE, payload)

    def commit(self):
        if not self._current_tx:
            raise RuntimeError("No active transaction")
        tx_id = self._current_tx
        self._append_record(self.TYPE_COMMIT, tx_id.encode('utf-8'))
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

    def checkpoint(self):
        payload = json.dumps(self.state).encode('utf-8')
        self._append_record(self.TYPE_CHECKPOINT, payload)

    def _append_record(self, record_type, payload):
        crc = zlib.crc32(payload) & 0xffffffff
        length = len(payload)
        header = struct.pack(">IBI", length, record_type, crc)
        with open(self.log_path, "ab") as f:
            f.write(header + payload)

    def recover(self, stop_on_corruption=True):
        self.state = {}
        if not os.path.exists(self.log_path):
            return
        
        with open(self.log_path, "rb") as f:
            data = f.read()

        offset = 0
        tx_ops = {}
        committed_txs = set()
        aborted_txs = set()
        records = []

        while offset < len(data):
            if offset + 9 > len(data):
                if stop_on_corruption:
                    raise CorruptedLogRecordError("Truncated header in WAL log")
                break
            length, rtype, expected_crc = struct.unpack(">IBI", data[offset:offset+9])
            offset += 9
            if offset + length > len(data):
                if stop_on_corruption:
                    raise CorruptedLogRecordError("Truncated payload in WAL log")
                break
            payload = data[offset:offset+length]
            offset += length

            actual_crc = zlib.crc32(payload) & 0xffffffff
            if actual_crc != expected_crc:
                raise CorruptedLogRecordError(f"CRC mismatch: expected {expected_crc}, got {actual_crc}")

            records.append((rtype, payload))

        # Replay records
        for rtype, payload in records:
            if rtype == self.TYPE_CHECKPOINT:
                self.state = json.loads(payload.decode('utf-8'))
                tx_ops.clear()
            elif rtype == self.TYPE_BEGIN:
                tx_id = payload.decode('utf-8')
                tx_ops[tx_id] = []
            elif rtype == self.TYPE_PUT:
                parts = payload.decode('utf-8').split(':', 2)
                tx_id, key, val = parts[0], parts[1], parts[2]
                if tx_id in tx_ops:
                    tx_ops[tx_id].append(('PUT', key, val))
            elif rtype == self.TYPE_DELETE:
                parts = payload.decode('utf-8').split(':', 1)
                tx_id, key = parts[0], parts[1]
                if tx_id in tx_ops:
                    tx_ops[tx_id].append(('DELETE', key))
            elif rtype == self.TYPE_COMMIT:
                tx_id = payload.decode('utf-8')
                if tx_id in tx_ops:
                    for op in tx_ops[tx_id]:
                        if op[0] == 'PUT':
                            self.state[op[1]] = op[2]
                        elif op[0] == 'DELETE':
                            self.state.pop(op[1], None)
                    del tx_ops[tx_id]
            elif rtype == self.TYPE_ABORT:
                tx_id = payload.decode('utf-8')
                tx_ops.pop(tx_id, None)

        return dict(self.state)
