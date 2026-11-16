import unittest
from store import Store

class StoreSmoke(unittest.TestCase):
    def test_inventory_lookup(self):
        self.assertEqual(Store({'a': 2}).inventory.available('a'), 2)
