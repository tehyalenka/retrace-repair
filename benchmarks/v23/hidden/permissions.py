import unittest
from directory import Directory
from documents import DocumentStore
from permissions import PermissionService
class PermissionVerification(unittest.TestCase):
 def setUp(self):
  self.s=PermissionService(Directory({'a':{'id':'a','teams':['red'],'active':True},'b':{'id':'b','teams':['blue'],'active':True},'c':{'id':'c','teams':['red'],'active':False}}),DocumentStore({'d':{'owner':'b','team':'red'},'e':{'owner':'a','team':None}}))
 def test_owner(self): self.assertTrue(self.s.can_access('b','d'))
 def test_team(self): self.assertTrue(self.s.can_access('a','d'))
 def test_no_cross_document_leak(self): self.assertFalse(self.s.can_access('b','e'))
 def test_inactive_owner_and_member(self): self.assertFalse(self.s.can_access('c','d'))
 def test_missing(self):
  self.assertFalse(self.s.can_access('missing','d')); self.assertFalse(self.s.can_access('a','missing'))
