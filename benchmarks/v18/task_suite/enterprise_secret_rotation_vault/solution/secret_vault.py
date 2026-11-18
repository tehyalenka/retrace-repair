import base64

class SecretRevokedError(Exception):
    pass

class SecretVault:
    def __init__(self, initial_secret):
        if not initial_secret or not isinstance(initial_secret, str):
            raise ValueError("initial_secret must be non-empty string")
        self.active_version = 1
        self.secrets = {1: {"secret": initial_secret, "status": "ACTIVE"}}

    def rotate(self, new_secret):
        if not new_secret or not isinstance(new_secret, str):
            raise ValueError("new_secret must be non-empty string")
        # Demote current ACTIVE to PREVIOUS (grace-period active for decryption)
        self.secrets[self.active_version]["status"] = "PREVIOUS"
        self.active_version += 1
        self.secrets[self.active_version] = {"secret": new_secret, "status": "ACTIVE"}

    def revoke(self, version):
        if not isinstance(version, int) or version not in self.secrets:
            raise ValueError(f"Invalid secret version: {version}")
        self.secrets[version]["status"] = "REVOKED"

    def encrypt(self, plaintext):
        if not isinstance(plaintext, str):
            raise ValueError("plaintext must be string")
        ver = self.active_version
        secret = self.secrets[ver]["secret"]
        key_bytes = secret.encode('utf-8')
        pt_bytes = plaintext.encode('utf-8')
        cipher_bytes = bytes([b ^ key_bytes[i % len(key_bytes)] for i, b in enumerate(pt_bytes)])
        encoded = base64.b64encode(cipher_bytes).decode('ascii')
        return f"v{ver}:{encoded}"

    def decrypt(self, token):
        if not token or not isinstance(token, str) or ":" not in token:
            raise ValueError("Invalid ciphertext token format")
        parts = token.split(":", 1)
        if not parts[0].startswith("v") or not parts[0][1:].isdigit():
            raise ValueError("Invalid version header")
        ver = int(parts[0][1:])
        if ver not in self.secrets:
            raise ValueError("Unknown secret version")

        status = self.secrets[ver]["status"]
        if status == "REVOKED":
            raise SecretRevokedError(f"Version {ver} is revoked")
        if status not in ("ACTIVE", "PREVIOUS"):
            raise ValueError(f"Version {ver} is not valid for decryption (status: {status})")

        secret = self.secrets[ver]["secret"]
        cipher_bytes = base64.b64decode(parts[1].encode('ascii'))
        key_bytes = secret.encode('utf-8')
        pt_bytes = bytes([b ^ key_bytes[i % len(key_bytes)] for i, b in enumerate(cipher_bytes)])
        return pt_bytes.decode('utf-8')
