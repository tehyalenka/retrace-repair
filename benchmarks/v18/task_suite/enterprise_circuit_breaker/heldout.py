import unittest
from storage import connect
from circuit import CircuitBreaker, CircuitBreakerOpenError

class Heldout(unittest.TestCase):
    def test_half_open_failure_immediately_reopens(self):
        cb = CircuitBreaker(connect(), failure_threshold=3, recovery_timeout=5.0)
        def fail(): raise IOError('fail')

        for _ in range(3):
            with self.assertRaises(IOError):
                cb.call('api', fail, now=10.0)

        self.assertEqual(cb.state('api', now=10.0), 'OPEN')
        self.assertEqual(cb.state('api', now=16.0), 'HALF_OPEN')

        # Single failure in HALF_OPEN trips immediately to OPEN
        with self.assertRaises(IOError):
            cb.call('api', fail, now=16.0)

        self.assertEqual(cb.state('api', now=17.0), 'OPEN')
        with self.assertRaises(CircuitBreakerOpenError):
            cb.call('api', lambda: 1, now=17.0)

    def test_success_resets_failure_count(self):
        cb = CircuitBreaker(connect(), failure_threshold=3)
        def fail(): raise ValueError('err')

        # 2 failures (threshold 3)
        for _ in range(2):
            with self.assertRaises(ValueError):
                cb.call('api', fail)
        self.assertEqual(cb.failure_count('api'), 2)

        # 1 success resets counter to 0
        cb.call('api', lambda: 'ok')
        self.assertEqual(cb.failure_count('api'), 0)
        self.assertEqual(cb.state('api'), 'CLOSED')

    def test_services_are_isolated(self):
        cb = CircuitBreaker(connect(), failure_threshold=1)
        with self.assertRaises(RuntimeError):
            cb.call('service-a', lambda: (_ for _ in ()).throw(RuntimeError('a failed')))

        self.assertEqual(cb.state('service-a'), 'OPEN')
        self.assertEqual(cb.state('service-b'), 'CLOSED')
        self.assertEqual(cb.call('service-b', lambda: 'ok'), 'ok')

    def test_invalid_parameters_rejected(self):
        d = connect()
        for bad in [0, -1, True, False, 1.5, '2']:
            with self.assertRaises(ValueError):
                CircuitBreaker(d, failure_threshold=bad)
        for bad_t in [0, -5.0, True, '10']:
            with self.assertRaises(ValueError):
                CircuitBreaker(d, recovery_timeout=bad_t)
