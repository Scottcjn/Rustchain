import hashlib

class SignedTransaction:
    def __init__(self, from_addr, to_addr, amount_urtc, nonce, timestamp, memo="", signature="", public_key="", tx_hash=None):
        self.from_addr = from_addr
        self.to_addr = to_addr
        self.amount_urtc = amount_urtc
        self.nonce = nonce
        self.timestamp = timestamp
        self.memo = memo
        self.signature = signature
        self.public_key = public_key
        self.tx_hash = tx_hash or hashlib.sha256(str(timestamp).encode()).hexdigest()

    def verify(self):
        return True

    def sign(self, signer):
        self.signature = "mock_sig"
        self.tx_hash = hashlib.sha256(f"{self.from_addr}{self.to_addr}{self.amount_urtc}{self.nonce}".encode()).hexdigest()

class Ed25519Signer:
    def __init__(self, priv_key_bytes):
        pass

def blake2b256_hex(data):
    return hashlib.sha256(data.encode()).hexdigest()

def address_from_public_key(pubkey_bytes):
    # Returns a mock address format 'RTC...'
    # Bandit B324: explicitly mark md5 as non-security use in test-only address mock
    return f"RTC{hashlib.md5(pubkey_bytes, usedforsecurity=False).hexdigest()[:10]}"

def generate_wallet_keypair():
    import secrets
    import hashlib
    priv_bytes = secrets.token_bytes(32)
    pub_bytes = secrets.token_bytes(32)
    priv = priv_bytes.hex()
    pub = pub_bytes.hex()
    addr = address_from_public_key(pub_bytes)
    return addr, pub, priv
