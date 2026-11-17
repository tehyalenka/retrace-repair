import unittest
from tokens import TokenStore
from gateway import Gateway
from access import Permissions
class Smoke(unittest.TestCase):
    def test_import(self):
        self.assertIsNotNone(Gateway(TokenStore(lambda: 0), Permissions(set())))
