import threading
import time

class ConnectionPoolExhaustedError(Exception):
    pass

class MockConnection:
    def __init__(self, conn_id):
        self.conn_id = conn_id
        self.alive = True

    def is_alive(self):
        return self.alive

    def close(self):
        self.alive = False

class _ConnectionContext:
    def __init__(self, pool, timeout=None):
        self.pool = pool
        self.timeout = timeout
        self.conn = None

    def __enter__(self):
        self.conn = self.pool.acquire(self.timeout)
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn is not None:
            self.pool.release(self.conn)

class ConnectionPool:
    def __init__(self, max_size=3, timeout=0.5):
        if not isinstance(max_size, int) or isinstance(max_size, bool) or max_size <= 0:
            raise ValueError("max_size must be positive integer")
        if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or timeout < 0:
            raise ValueError("timeout must be non-negative number")

        self.max_size = max_size
        self.timeout = float(timeout)
        self._cond = threading.Condition(threading.Lock())
        self.available = []
        self._total_created = 0
        self._counter = 0

    def get_connection(self, timeout=None):
        return _ConnectionContext(self, timeout)

    def acquire(self, timeout=None):
        to = self.timeout if timeout is None else timeout
        start = time.time()

        with self._cond:
            while True:
                # 1. Check existing available connections
                while self.available:
                    conn = self.available.pop()
                    if conn.is_alive():
                        return conn
                    # Dead connection: discard and decrement active total
                    self._total_created -= 1

                # 2. Check if we can allocate a new connection within max_size
                if self._total_created < self.max_size:
                    self._counter += 1
                    self._total_created += 1
                    return MockConnection(self._counter)

                # 3. Wait for a released connection
                elapsed = time.time() - start
                remaining = to - elapsed
                if remaining <= 0:
                    raise ConnectionPoolExhaustedError(
                        f"Pool exhausted: all {self.max_size} connections checked out"
                    )
                self._cond.wait(timeout=remaining)

    def release(self, conn):
        if not isinstance(conn, MockConnection):
            raise ValueError("Invalid connection")
        with self._cond:
            if conn.is_alive():
                self.available.append(conn)
            else:
                self._total_created -= 1
            self._cond.notify()
