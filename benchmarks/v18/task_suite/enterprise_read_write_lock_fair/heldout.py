import unittest
import threading
import time
from rwlock import FairReadWriteLock

class Heldout(unittest.TestCase):
    def test_writer_mutual_exclusion(self):
        lock = FairReadWriteLock()
        lock.acquire_write()

        other_reader_acquired = [False]
        def reader():
            other_reader_acquired[0] = lock.acquire_read(timeout=0.1)

        t = threading.Thread(target=reader, daemon=True)
        t.start()
        t.join(timeout=1.0)
        self.assertFalse(other_reader_acquired[0])

        lock.release_write()

    def test_context_managers(self):
        lock = FairReadWriteLock()
        with lock.read_lock() as ctx:
            self.assertIsNotNone(ctx)
            with lock.read_lock() as ctx2:
                self.assertIsNotNone(ctx2)

        with lock.write_lock() as wctx:
            self.assertIsNotNone(wctx)

    def test_release_underflow_raises_runtime_error(self):
        lock = FairReadWriteLock()
        with self.assertRaises(RuntimeError):
            lock.release_read()
        with self.assertRaises(RuntimeError):
            lock.release_write()

    def test_acquisition_timeout(self):
        lock = FairReadWriteLock()
        lock.acquire_write()
        self.assertFalse(lock.acquire_write(timeout=0.05))
        self.assertFalse(lock.acquire_read(timeout=0.05))
        lock.release_write()
