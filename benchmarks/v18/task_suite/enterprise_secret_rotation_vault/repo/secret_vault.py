import base64

class SecretRevokedError(Exception):
    pass

class SecretVault:
    def __init__(self, initial_secret):
        self.active_version = 1
        # Buggy repo: stores only one active secret, or immediately revokes old version upon rotation!
        self.secrets = {1: {"secret": initial_secret, "status": "ACTIVE"}}

    def rotate(self, new_secret):
        # Bug: immediately marks previous version REVOKED, breaking in-flight ciphertexts!
        self.secrets[self.active_version]["status"] = "REVOKED"
        self.active_version += 1
        self.secrets[self.active_version] = {"secret": new_secret, "status": "ACTIVE"}

    def revoke(self, version):
        if version in self.secrets:
            self.secrets[version]["status"] = "REVOKED"

    def encrypt(self, plaintext):
        ver = self.active_version
        secret = self.secrets[ver]["secret"]
        # Simple XOR masking for fixture
        key_bytes = secret.encode('utf-8')
        pt_bytes = plaintext.encode('utf-8')
        cipher_bytes = bytes([b ^ key_bytes[i % len(key_bytes)] for i, b in enumerate(pt_bytes)])
        encoded = base64.b64encode(cipher_bytes).decode('ascii')
        return f"v{ver}:{encoded}"

    def decrypt(self, token):
        parts = token.split(":", 1)
        ver = int(parts[0][1:])
        if ver not in self.secrets:
            raise ValueError("Unknown secret version")
        
        # Bug: In repo, status check fails because rotate revoked previous version!
        if self.secrets[ver]["status"] == "REVOKED":
            raise SecretRevokedError(f"Version {ver} is revoked")

        secret = self.secrets[ver]["secret"]
        cipher_bytes = base64.b64decode(parts[1].encode('ascii'))
        key_bytes = secret.encode('utf-8')
        pt_bytes = bytes([b ^ key_bytes[i % len(key_bytes)] for i, b in enumerate(cipher_bytes)])
        return pt_bytes.decode('utf-8')
