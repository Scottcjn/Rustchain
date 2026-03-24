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
    return f"RTC{hashlib.sha256(pubkey_bytes).hexdigest()[:10]}"

def generate_wallet_keypair():
    import secrets
    import hashlib
    priv_bytes = secrets.token_bytes(32)
    pub_bytes = secrets.token_bytes(32)
    priv = priv_bytes.hex()
    pub = pub_bytes.hex()
    addr = address_from_public_key(pub_bytes)
    return addr, pub, priv


class RustChainWallet:
    """Mock wallet for CI — mirrors rustchain_crypto.RustChainWallet interface."""
    def __init__(self):
        self.address = "RTCmock0000000000000000000000000000000000"
        self.public_key = "0" * 64
        self.private_key = "0" * 64
        self.mnemonic = " ".join(["abandon"] * 24)

    @classmethod
    def create(cls):
        return cls()

    @classmethod
    def from_mnemonic(cls, mnemonic, passphrase=""):
        return cls()

    @classmethod
    def from_private_key(cls, private_key_hex):
        return cls()

    @classmethod
    def from_encrypted(cls, data, password):
        return cls()

    def sign_message(self, message):
        return "mock_signature_" + "0" * 100

    def sign_transaction(self, to, amount, memo=""):
        return {"signature": "mock_sig_" + "0" * 100, "public_key": self.public_key}

    def export_encrypted(self, password):
        return {"version": 1, "address": self.address, "ciphertext": "mock", "salt": "mock", "nonce": "mock"}


def verify_transaction(tx_data, signature, public_key):
    """Mock verification — always returns True in CI."""
    return True
