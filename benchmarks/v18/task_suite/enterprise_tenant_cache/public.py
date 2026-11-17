import unittest
from storage import connect
from authorization import Authorization
class Public(unittest.TestCase):
 def test_tenant_isolation(self):
  a=Authorization(connect());a.set_permission('alpha','user','doc',True)
  self.assertTrue(a.can_read('alpha','user','doc'))
  self.assertFalse(a.can_read('beta','user','doc'))
 def test_invalid_identity_returns_false(self):
  a=Authorization(connect())
  self.assertIs(a.can_read('','user','doc'), False)
  self.assertIs(a.can_read('alpha','','doc'), False)
  self.assertIs(a.can_read('alpha','user',''), False)
