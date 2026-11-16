import unittest
from auth import authenticate

class AuthenticationTests(unittest.TestCase):
    def test_valid(self):
        self.assertTrue(authenticate("admin", "secret"))

    def test_invalid(self):
        self.assertFalse(authenticate("guest", "secret"))

if __name__ == "__main__":
    unittest.main()
