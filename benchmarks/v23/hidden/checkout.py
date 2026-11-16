import unittest
from checkout import Checkout
from inventory import Inventory
from payments import PaymentGateway
class CheckoutVerification(unittest.TestCase):
 def setUp(self):
  self.i=Inventory({'A':5,'B':2},{'A':10,'B':7}); self.g=PaymentGateway(); self.c=Checkout(self.i,self.g)
 def test_aggregate_duplicate_sku(self):
  r=self.c.place('x',[('A',2),('A',2)]); self.assertEqual(r['total'],40); self.assertEqual(self.i.stock['A'],1); self.assertEqual(self.g.charges,[('x',40)])
 def test_idempotent_order(self):
  a=self.c.place('x',[('A',1)]); b=self.c.place('x',[('B',1)]); self.assertEqual(a,b); self.assertEqual(self.i.stock['B'],2); self.assertEqual(len(self.g.charges),1)
 def test_insufficient_is_atomic(self):
  with self.assertRaises(ValueError): self.c.place('x',[('A',1),('B',3)])
  self.assertEqual(self.i.stock,{'A':5,'B':2}); self.assertEqual(self.g.charges,[])
 def test_decline_is_atomic(self):
  self.g.decline=True
  with self.assertRaises(ValueError): self.c.place('x',[('A',1)])
  self.assertEqual(self.i.stock['A'],5); self.assertEqual(self.c.orders,{})
 def test_invalid_and_unknown(self):
  for items in ([('A',0)],[('Z',1)],[('A',True)],[]):
   with self.assertRaises(ValueError): self.c.place('x',items)
