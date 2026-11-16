import unittest
from store import Store

class IndependentOrderTests(unittest.TestCase):
    def test_success_and_decrement(self):
        store=Store({'a': 3, 'b': 2})
        self.assertEqual(store.purchase({'a': 2, 'b': 1}), {'accepted': True})
        self.assertEqual(store.inventory.available('a'), 1)
        self.assertEqual(store.inventory.available('b'), 1)
    def test_insufficient_stock_atomic(self):
        store=Store({'a': 2, 'b': 1})
        self.assertEqual(store.purchase({'a': 1, 'b': 2}), {'accepted': False, 'reason': 'insufficient_stock'})
        self.assertEqual(store.inventory.available('a'), 2)
    def test_unknown_sku(self):
        store=Store({'a': 2})
        self.assertEqual(store.purchase({'z': 1}), {'accepted': False, 'reason': 'insufficient_stock'})
    def test_invalid_quantity(self):
        store=Store({'a': 2})
        with self.assertRaises(ValueError): store.purchase({'a': 0})
        self.assertEqual(store.inventory.available('a'), 2)
    def test_repeat_purchase(self):
        store=Store({'a': 2})
        self.assertEqual(store.purchase({'a': 1}), {'accepted': True})
        self.assertEqual(store.purchase({'a': 2}), {'accepted': False, 'reason': 'insufficient_stock'})
