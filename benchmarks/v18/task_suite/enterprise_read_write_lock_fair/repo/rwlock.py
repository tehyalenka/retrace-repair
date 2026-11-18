import threading
import time

class FairReadWriteLock:
    def __init__(self):
        self._cond = threading.Condition(threading.Lock())
        self._readers = 0
        self._writer = False
        self._waiting_writers = 0

    def acquire_read(self, timeout=None):
        start = time.time()
        with self._cond:
            # Buggy repo: ignores self._waiting_writers!
            # Allows readers to jump ahead of waiting writers, causing writer starvation.
            while self._writer:
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
            if self._readers > 0:
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
            self._writer = False
            self._cond.notify_all()
