import unittest
from tokens import TokenStore
from gateway import Gateway
from access import Permissions

class SessionVerification(unittest.TestCase):
    def setUp(self):
        self.now = [100]
        self.tokens = TokenStore(lambda: self.now[0])
        self.gateway = Gateway(self.tokens, Permissions({('alice', 'file1')}))
    def test_issue_resolve_and_expire(self):
        self.tokens.issue('t', 'alice', 10)
        self.assertEqual(self.tokens.resolve('t'), 'alice')
        self.now[0] = 110
        self.assertIsNone(self.tokens.resolve('t'))
    def test_gateway_authorization(self):
        self.tokens.issue('t', 'alice', 10)
        self.assertTrue(self.gateway.allowed('t', 'file1'))
        self.assertFalse(self.gateway.allowed('t', 'file2'))
        self.assertFalse(self.gateway.allowed('missing', 'file1'))
    def test_revocation(self):
        self.tokens.issue('t', 'alice', 10)
        self.assertTrue(self.tokens.revoke('t'))
        self.assertFalse(self.tokens.revoke('t'))
        self.assertIsNone(self.tokens.resolve('t'))
        self.assertFalse(self.gateway.allowed('t', 'file1'))
    def test_invalid_issue(self):
        for token, user, ttl in (('', 'alice', 2), ('t', '', 2), ('t', 'alice', 0),
                                 ('t', 'alice', True), ('t', 'alice', 1.2)):
            with self.subTest(args=(token, user, ttl)), self.assertRaises(ValueError):
                self.tokens.issue(token, user, ttl)
    def test_token_reuse_rejected(self):
        self.tokens.issue('t', 'alice', 1)
        self.now[0] = 200
        with self.assertRaises(ValueError):
            self.tokens.issue('t', 'bob', 10)
    def test_missing_and_expired(self):
        self.assertIsNone(self.tokens.resolve('unknown'))
        self.assertFalse(self.tokens.revoke('unknown'))
        self.tokens.issue('t', 'alice', 1)
        self.now[0] = 101
        self.assertFalse(self.gateway.allowed('t', 'file1'))
