import unittest
from storage import connect
from ledger import Ledger
class Public(unittest.TestCase):
 def test_duplicate_delivery(self):
  l=Ledger(connect());self.assertEqual(l.post('e1','A',100),100)
  self.assertEqual(l.post('e1','A',100),100)
  self.assertEqual(l.balance('A'),100)
