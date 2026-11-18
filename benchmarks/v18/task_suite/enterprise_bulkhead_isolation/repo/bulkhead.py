import threading

class BulkheadFullError(Exception):
    pass

class TenantBulkhead:
    def __init__(self, max_concurrent=2, max_queue_size=2):
        self.max_concurrent = max_concurrent
        self.max_queue_size = max_queue_size
        self.lock = threading.Lock()
        
        # Buggy repo: Global counters shared across ALL tenants!
        # A single tenant saturates the bulkhead, starving all other tenants!
        self.global_active = 0
        self.global_queue = 0

    def execute(self, tenant_id, func, *args, **kwargs):
        with self.lock:
            # Bug: ignores tenant_id, checks global limit
            if self.global_active >= self.max_concurrent:
                if self.global_queue >= self.max_queue_size:
                    raise BulkheadFullError("Bulkhead capacity reached")
                self.global_queue += 1
            else:
                self.global_active += 1

        try:
            return func(*args, **kwargs)
        finally:
            with self.lock:
                if self.global_active > 0:
                    self.global_active -= 1
