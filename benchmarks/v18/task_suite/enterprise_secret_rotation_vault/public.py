import unittest
from secret_vault import SecretVault, SecretRevokedError

class Public(unittest.TestCase):
    def test_encrypt_and_decrypt_basic(self):
        vault = SecretVault("initial-super-secret-key-1")
        token = vault.encrypt("hello enterprise world")
        self.assertTrue(token.startswith("v1:"))
        decrypted = vault.decrypt(token)
        self.assertEqual(decrypted, "hello enterprise world")

    def test_zero_downtime_rotation_grace_period(self):
        vault = SecretVault("initial-key-1")
        # Token generated before rotation
        old_token = vault.encrypt("payload-before-rotation")

        # Rotate to key 2
        vault.rotate("new-key-2")
        # Newly encrypted tokens use v2
        new_token = vault.encrypt("payload-after-rotation")
        self.assertTrue(new_token.startswith("v2:"))

        # Both new and old tokens MUST decrypt cleanly without error!
        self.assertEqual(vault.decrypt(new_token), "payload-after-rotation")
        self.assertEqual(vault.decrypt(old_token), "payload-before-rotation")
