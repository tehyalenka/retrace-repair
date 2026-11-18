import threading
import time

class StampedeCache:
    def __init__(self):
        self.cache = {} # key -> (value, expires_at)
        self.lock = threading.Lock()

    def get_or_compute(self, key, loader, ttl_seconds, now=None):
        now = time.time() if now is None else now
        
        # Buggy repo: no single-flight coalescing
        # Whenever cache is empty or expired, EVERY caller calls loader() directly!
        with self.lock:
            if key in self.cache:
                val, expires_at = self.cache[key]
                if expires_at > now:
                    return val

        # Thundering herd bug: loader() executed outside lock without single-flight protection
        val = loader()

        with self.lock:
            self.cache[key] = (val, now + ttl_seconds)
        return val
