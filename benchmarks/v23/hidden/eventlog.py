import unittest
from eventlog import EventLog
class EventVerification(unittest.TestCase):
 def setUp(self): self.l=EventLog()
 def test_order_and_balance(self):
  self.assertEqual(self.l.append('1','a',10),10); self.assertEqual(self.l.append('2','a',-4),6); self.assertEqual(self.l.balance('a'),6)
 def test_duplicate_idempotent(self):
  self.l.append('1','a',10); self.assertEqual(self.l.append('1','a',10),10); self.assertEqual(len(self.l.store.all()),1)
 def test_conflicting_id(self):
  self.l.append('1','a',10)
  with self.assertRaises(ValueError): self.l.append('1','a',11)
 def test_overdraft_atomic(self):
  with self.assertRaises(ValueError): self.l.append('x','a',-1)
  self.assertEqual(self.l.store.all(),[])
 def test_invalid_delta(self):
  for x in (True,1.5,'3'):
   with self.assertRaises(ValueError): self.l.append('x','a',x)
