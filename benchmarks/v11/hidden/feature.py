import unittest
from bank import Bank

class TransferVerification(unittest.TestCase):
    def test_success_and_order(self):
        b = Bank({'a': 10, 'b': 0, 'c': 0})
        self.assertEqual(b.transfer_many([('a','b',7), ('b','c',5)]), {'a': 3, 'b': 2, 'c': 5})
        self.assertEqual(b.balance('c'), 5)
    def test_atomic_overdraft(self):
        b = Bank({'a': 10, 'b': 0})
        with self.assertRaises(ValueError): b.transfer_many([('a','b',8), ('a','b',3)])
        self.assertEqual((b.balance('a'),b.balance('b')), (10,0))
    def test_validate_all(self):
        b = Bank({'a': 10, 'b': 0})
        for batch in ([('a','b',2), ('b','missing',1)], [('a','b',2), ('b','a',0)], [('a','b',True)]):
            with self.subTest(batch=batch):
                with self.assertRaises(ValueError): b.transfer_many(batch)
                self.assertEqual((b.balance('a'),b.balance('b')), (10,0))
    def test_existing_api(self):
        b = Bank({'a': 5, 'b': 0})
        b.transfer('a','b',2)
        self.assertEqual(b.balance('a'), 3)
    def test_empty(self):
        b = Bank({'a': 5})
        self.assertEqual(b.transfer_many([]), {'a': 5})
