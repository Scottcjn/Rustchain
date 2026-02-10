import hashlib
import json
import base64
import time
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

class RustChainCrypto:
    @staticmethod
    def generate_keypair():
        private_key = ed25519.Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        
        priv_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption()
        )
        pub_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        return priv_bytes.hex(), pub_bytes.hex()

    @staticmethod
    def get_address(pub_key_hex):
        # RustChain Address: RTC + SHA256(pub_key_bytes)[:40]
        pub_bytes = bytes.fromhex(pub_key_hex)
        addr_hash = hashlib.sha256(pub_bytes).hexdigest()[:40]
        return f"RTC{addr_hash}"

    @staticmethod
    def sign_transaction(priv_key_hex, to_address, amount_rtc, memo=""):
        priv_bytes = bytes.fromhex(priv_key_hex)
        private_key = ed25519.Ed25519PrivateKey.from_private_bytes(priv_bytes)
        public_key = private_key.public_key()
        pub_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        
        from_address = RustChainCrypto.get_address(pub_bytes.hex())
        timestamp = int(time.time())
        
        # Canonical transaction data for signing
        tx_data = {
            "from": from_address,
            "to": to_address,
            "amount_rtc": float(amount_rtc),
            "memo": memo,
            "timestamp": timestamp,
            "public_key": pub_bytes.hex()
        }
        
        message = json.dumps(tx_data, sort_keys=True).encode()
        signature = private_key.sign(message)
        
        tx_data["signature"] = signature.hex()
        return tx_data

