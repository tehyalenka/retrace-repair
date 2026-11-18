import unittest
from secret_vault import SecretVault, SecretRevokedError

class Heldout(unittest.TestCase):
    def test_explicit_revocation_blocks_decryption(self):
        vault = SecretVault("key-1")
        token_v1 = vault.encrypt("data-v1")

        vault.rotate("key-2")
        # Explicitly revoke v1 (compromised key emergency)
        vault.revoke(1)

        with self.assertRaises(SecretRevokedError):
            vault.decrypt(token_v1)

        # v2 should still work
        token_v2 = vault.encrypt("data-v2")
        self.assertEqual(vault.decrypt(token_v2), "data-v2")

    def test_invalid_tokens_raise_value_error(self):
        vault = SecretVault("key-1")
        with self.assertRaises(ValueError):
            vault.decrypt("bad-token-without-colon")
        with self.assertRaises(ValueError):
            vault.decrypt("v999:bm9uZQ==")
        with self.assertRaises(ValueError):
            vault.decrypt("vx:bm9uZQ==")

    def test_invalid_parameters_raise_value_error(self):
        with self.assertRaises(ValueError):
            SecretVault("")
        vault = SecretVault("valid")
        with self.assertRaises(ValueError):
            vault.rotate("")
        with self.assertRaises(ValueError):
            vault.encrypt(123)
        with self.assertRaises(ValueError):
            vault.revoke(99)
