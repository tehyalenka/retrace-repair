import unittest
from storage import connect
from orders import OrderService
class Heldout(unittest.TestCase):
 def test_reuse_key_conflicting_payload(self):
  d=connect();s=OrderService(d);s.seed('A',7);s.place('x','A',2)
  with self.assertRaises(ValueError): s.place('x','A',3)
  self.assertEqual(s.available('A'),5)
 def test_idempotent_replay_success(self):
  d=connect();s=OrderService(d);s.seed('A',7)
  self.assertTrue(s.place('x','A',2))
  self.assertTrue(s.place('x','A',2))
  self.assertEqual(s.available('A'),5)
 def test_failed_stock_never_emits(self):
  d=connect();s=OrderService(d);s.seed('A',1)
  self.assertFalse(s.place('a','A',2));self.assertEqual(s.event_count(),0)
 def test_rollback_on_outbox_error(self):
  d=connect();s=OrderService(d);s.seed('A',4)
  d.execute('CREATE TRIGGER deny_event BEFORE INSERT ON outbox BEGIN SELECT RAISE(ABORT, "outbox unavailable"); END;');d.commit()
  with self.assertRaises(Exception):s.place('r','A',2)
  self.assertEqual(s.available('A'),4)
  self.assertEqual(d.execute('SELECT count(*) FROM orders').fetchone()[0],0)
 def test_distinct_requests_and_no_oversell(self):
  d=connect();s=OrderService(d);s.seed('A',3)
  self.assertTrue(s.place('a','A',2));self.assertFalse(s.place('b','A',2))
  self.assertEqual(s.available('A'),1);self.assertEqual(s.event_count(),1)
 def test_invalid_qty(self):
  d=connect();s=OrderService(d);s.seed('A',5)
  for q in [0,-1,True,1.5]:
   with self.assertRaises(ValueError):s.place('x','A',q)
  self.assertEqual(s.available('A'),5)
