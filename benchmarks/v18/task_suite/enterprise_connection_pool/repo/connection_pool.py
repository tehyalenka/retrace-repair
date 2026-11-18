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

class ConnectionPool:
    def __init__(self, max_size=3, timeout=0.5):
        self.max_size = max_size
        self.timeout = timeout
        self.available = []
        self._counter = 0

    def acquire(self, timeout=None):
        # Buggy repo: Unbounded allocation!
        # If available list is empty, it blindly creates new connections indefinitely!
        if self.available:
            return self.available.pop()
        
        # Bug: ignores max_size!
        self._counter += 1
        return MockConnection(self._counter)

    def release(self, conn):
        self.available.append(conn)
