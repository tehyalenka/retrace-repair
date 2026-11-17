import unittest
from storage import connect
from circuit import CircuitBreaker, CircuitBreakerOpenError

class Public(unittest.TestCase):
    def test_successful_call(self):
        cb = CircuitBreaker(connect(), failure_threshold=2)
        res = cb.call('api', lambda: 42)
        self.assertEqual(res, 42)
        self.assertEqual(cb.state('api'), 'CLOSED')

    def test_trips_to_open_after_threshold_failures(self):
        cb = CircuitBreaker(connect(), failure_threshold=2)
        def fail():
            raise ConnectionError('down')

        for _ in range(2):
            with self.assertRaises(ConnectionError):
                cb.call('api', fail)

        self.assertEqual(cb.state('api'), 'OPEN')
        with self.assertRaises(CircuitBreakerOpenError):
            cb.call('api', lambda: 1)

    def test_half_open_recovery_after_timeout(self):
        cb = CircuitBreaker(connect(), failure_threshold=1, recovery_timeout=10.0)
        def fail(): raise ValueError('err')
        with self.assertRaises(ValueError):
            cb.call('api', fail, now=100.0)

        self.assertEqual(cb.state('api', now=105.0), 'OPEN')
        self.assertEqual(cb.state('api', now=111.0), 'HALF_OPEN')

        # Successful probe call in HALF_OPEN resets to CLOSED
        res = cb.call('api', lambda: 'recovered', now=112.0)
        self.assertEqual(res, 'recovered')
        self.assertEqual(cb.state('api', now=112.0), 'CLOSED')
