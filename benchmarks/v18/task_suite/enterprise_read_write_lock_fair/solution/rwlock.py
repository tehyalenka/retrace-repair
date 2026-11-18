import threading
import time

class ReadLockContext:
    def __init__(self, rwlock, timeout=None):
        self.rwlock = rwlock
        self.timeout = timeout

    def __enter__(self):
        acquired = self.rwlock.acquire_read(timeout=self.timeout)
        if not acquired:
            raise TimeoutError("Failed to acquire read lock")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.rwlock.release_read()

class WriteLockContext:
    def __init__(self, rwlock, timeout=None):
        self.rwlock = rwlock
        self.timeout = timeout

    def __enter__(self):
        acquired = self.rwlock.acquire_write(timeout=self.timeout)
        if not acquired:
            raise TimeoutError("Failed to acquire write lock")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.rwlock.release_write()

class FairReadWriteLock:
    def __init__(self):
        self._cond = threading.Condition(threading.Lock())
        self._readers = 0
        self._writer = False
        self._waiting_writers = 0

    def read_lock(self, timeout=None):
        return ReadLockContext(self, timeout)

    def write_lock(self, timeout=None):
        return WriteLockContext(self, timeout)

    def acquire_read(self, timeout=None):
        start = time.time()
        with self._cond:
            while self._writer or self._waiting_writers > 0:
                if timeout is not None:
                    elapsed = time.time() - start
                    rem = timeout - elapsed
                    if rem <= 0:
                        return False
                    self._cond.wait(timeout=rem)
                else:
                    self._cond.wait(timeout=1.0)
            self._readers += 1
            return True

    def release_read(self):
        with self._cond:
            if self._readers <= 0:
                raise RuntimeError("Cannot release unacquired read lock")
            self._readers -= 1
            if self._readers == 0:
                self._cond.notify_all()

    def acquire_write(self, timeout=None):
        start = time.time()
        with self._cond:
            self._waiting_writers += 1
            try:
                while self._writer or self._readers > 0:
                    if timeout is not None:
                        elapsed = time.time() - start
                        rem = timeout - elapsed
                        if rem <= 0:
                            return False
                        self._cond.wait(timeout=rem)
                    else:
                        self._cond.wait(timeout=1.0)
                self._writer = True
                return True
            finally:
                self._waiting_writers -= 1

    def release_write(self):
        with self._cond:
            if not self._writer:
                raise RuntimeError("Cannot release unacquired write lock")
            self._writer = False
            self._cond.notify_all()
