import threading
import time

class StampedeCache:
    def __init__(self):
        self.cache = {} # key -> (value, expires_at)
        self.lock = threading.Lock()
        self._in_flight = {} # key -> (threading.Event(), holder)

    def get_or_compute(self, key, loader, ttl_seconds, now=None):
        if not key or not isinstance(key, str):
            raise ValueError("key must be non-empty string")
        if not callable(loader):
            raise ValueError("loader must be callable")
        if not isinstance(ttl_seconds, (int, float)) or isinstance(ttl_seconds, bool) or ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive number")

        now = time.time() if now is None else now

        event = None
        holder = None
        is_leader = False

        with self.lock:
            # Check cache
            if key in self.cache:
                val, expires_at = self.cache[key]
                if expires_at > now:
                    return val

            # Check single-flight in progress
            if key in self._in_flight:
                event, holder = self._in_flight[key]
            else:
                event = threading.Event()
                holder = {"result": None, "error": None}
                self._in_flight[key] = (event, holder)
                is_leader = True

        if not is_leader:
            event.wait(timeout=5.0)
            if holder["error"] is not None:
                raise holder["error"]
            return holder["result"]

        # Leader computes
        try:
            val = loader()
            holder["result"] = val
            with self.lock:
                self.cache[key] = (val, now + ttl_seconds)
            return val
        except Exception as err:
            holder["error"] = err
            raise
        finally:
            with self.lock:
                self._in_flight.pop(key, None)
            event.set()
