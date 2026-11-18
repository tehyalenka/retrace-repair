import threading

class BulkheadFullError(Exception):
    pass

class _TenantPool:
    def __init__(self, max_concurrent, max_queue_size):
        self.max_concurrent = max_concurrent
        self.max_queue_size = max_queue_size
        self.active = 0
        self.waiting = 0
        self.cond = threading.Condition(threading.Lock())

class TenantBulkhead:
    def __init__(self, max_concurrent=2, max_queue_size=2):
        if not isinstance(max_concurrent, int) or isinstance(max_concurrent, bool) or max_concurrent <= 0:
            raise ValueError("max_concurrent must be positive int")
        if not isinstance(max_queue_size, int) or isinstance(max_queue_size, bool) or max_queue_size < 0:
            raise ValueError("max_queue_size must be non-negative int")

        self.max_concurrent = max_concurrent
        self.max_queue_size = max_queue_size
        self._pools_lock = threading.Lock()
        self._pools = {}

    def _get_pool(self, tenant_id):
        with self._pools_lock:
            if tenant_id not in self._pools:
                self._pools[tenant_id] = _TenantPool(self.max_concurrent, self.max_queue_size)
            return self._pools[tenant_id]

    def execute(self, tenant_id, func, *args, **kwargs):
        if not tenant_id or not isinstance(tenant_id, str):
            raise ValueError("tenant_id must be non-empty string")
        if not callable(func):
            raise ValueError("func must be callable")

        pool = self._get_pool(tenant_id)
        with pool.cond:
            if pool.active < pool.max_concurrent:
                pool.active += 1
            elif pool.waiting < pool.max_queue_size:
                pool.waiting += 1
                try:
                    while pool.active >= pool.max_concurrent:
                        pool.cond.wait()
                    pool.waiting -= 1
                    pool.active += 1
                except Exception:
                    pool.waiting -= 1
                    raise
            else:
                raise BulkheadFullError(f"Bulkhead for tenant '{tenant_id}' is full")

        try:
            return func(*args, **kwargs)
        finally:
            with pool.cond:
                pool.active -= 1
                pool.cond.notify()
