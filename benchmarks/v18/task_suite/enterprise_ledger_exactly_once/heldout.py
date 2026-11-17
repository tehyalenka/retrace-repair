import unittest
from storage import connect
from ledger import Ledger
class Heldout(unittest.TestCase):
 def test_conflicting_duplicate(self):
  l=Ledger(connect());l.post('e1','A',100)
  with self.assertRaises(ValueError):l.post('e1','B',100)
  self.assertEqual(l.balance('A'),100);self.assertEqual(l.balance('B'),0)
 def test_signed_entries_and_replays(self):
  l=Ledger(connect())
  for i,c in enumerate([105,-20,30,-10]):l.post(str(i),'A',c)
  for i,c in enumerate([105,-20,30,-10]):l.post(str(i),'A',c)
  self.assertEqual(l.balance('A'),105)
 def test_atomicity_when_balance_write_fails(self):
  d=connect();l=Ledger(d)
  d.execute('CREATE TRIGGER deny_balance BEFORE INSERT ON balances BEGIN SELECT RAISE(ABORT,"db failure"); END;');d.commit()
  with self.assertRaises(Exception):l.post('x','A',10)
  self.assertEqual(d.execute('SELECT count(*) FROM ledger').fetchone()[0],0)
 def test_reject_bad_entries(self):
  l=Ledger(connect())
  for eid,account,amount in [('', 'A',1),('x','',1),('x','A',0),('x','A',True),('x','A',1.5)]:
   with self.assertRaises(ValueError):l.post(eid,account,amount)
