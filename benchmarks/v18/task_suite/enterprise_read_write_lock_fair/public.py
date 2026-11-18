import unittest
import threading
import time
from rwlock import FairReadWriteLock

class Public(unittest.TestCase):
    def test_concurrent_readers(self):
        lock = FairReadWriteLock()
        self.assertTrue(lock.acquire_read(timeout=0.5))
        self.assertTrue(lock.acquire_read(timeout=0.5))
        lock.release_read()
        lock.release_read()

    def test_writer_starvation_prevention(self):
        lock = FairReadWriteLock()
        self.assertTrue(lock.acquire_read(timeout=0.5)) # Active reader holds lock

        writer_started = threading.Event()
        writer_acquired = threading.Event()

        def writer_job():
            writer_started.set()
            if lock.acquire_write(timeout=1.0):
                writer_acquired.set()
                lock.release_write()

        t_writer = threading.Thread(target=writer_job, daemon=True)
        t_writer.start()
        if not writer_started.wait(timeout=1.0):
            self.fail("Timed out waiting for writer thread")
        time.sleep(0.05) # Ensure writer enters wait and registers waiting_writer

        try:
            # New reader tries to acquire with short timeout: MUST fail because writer is waiting
            new_reader_acquired = lock.acquire_read(timeout=0.1)
            self.assertFalse(new_reader_acquired, "New reader jumped ahead of waiting writer!")
        finally:
            lock.release_read()

        t_writer.join(timeout=1.0)
        self.assertTrue(writer_acquired.is_set())
