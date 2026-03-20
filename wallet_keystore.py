// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import os
import json
import hashlib
import secrets
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
import base64
import sqlite3

DEFAULT_KEYSTORE_PATH = "rustchain_wallet.keystore"
DB_PATH = "rustchain.db"

class WalletKeystore:
    def __init__(self, keystore_path=DEFAULT_KEYSTORE_PATH):
        self.keystore_path = keystore_path
        self.salt_length = 32
        self.nonce_length = 12
        self.key_iterations = 100000

    def _derive_key(self, password, salt):
        """Derive encryption key from password using PBKDF2"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=self.key_iterations,
            backend=default_backend()
        )
        return kdf.derive(password.encode())

    def create_wallet(self, password, private_key, public_key, address):
        """Create encrypted keystore file"""
        salt = secrets.token_bytes(self.salt_length)
        key = self._derive_key(password, salt)

        wallet_data = {
            'private_key': private_key,
            'public_key': public_key,
            'address': address,
            'created_at': secrets.token_hex(8)
        }

        aesgcm = AESGCM(key)
        nonce = secrets.token_bytes(self.nonce_length)

        plaintext = json.dumps(wallet_data).encode()
        ciphertext = aesgcm.encrypt(nonce, plaintext, None)

        keystore = {
            'version': '1.0',
            'salt': base64.b64encode(salt).decode(),
            'nonce': base64.b64encode(nonce).decode(),
            'ciphertext': base64.b64encode(ciphertext).decode(),
            'iterations': self.key_iterations
        }

        with open(self.keystore_path, 'w') as f:
            json.dump(keystore, f, indent=2)

        return True

    def unlock_wallet(self, password):
        """Decrypt and load wallet from keystore"""
        if not os.path.exists(self.keystore_path):
            return None

        try:
            with open(self.keystore_path, 'r') as f:
                keystore = json.load(f)

            salt = base64.b64decode(keystore['salt'])
            nonce = base64.b64decode(keystore['nonce'])
            ciphertext = base64.b64decode(keystore['ciphertext'])

            key = self._derive_key(password, salt)
            aesgcm = AESGCM(key)

            plaintext = aesgcm.decrypt(nonce, ciphertext, None)
            wallet_data = json.loads(plaintext.decode())

            return wallet_data

        except Exception:
            return None

    def change_password(self, old_password, new_password):
        """Change keystore password"""
        wallet_data = self.unlock_wallet(old_password)
        if not wallet_data:
            return False

        return self.create_wallet(
            new_password,
            wallet_data['private_key'],
            wallet_data['public_key'],
            wallet_data['address']
        )

    def backup_keystore(self, backup_path):
        """Create backup of keystore file"""
        if not os.path.exists(self.keystore_path):
            return False

        try:
            with open(self.keystore_path, 'rb') as src:
                with open(backup_path, 'wb') as dst:
                    dst.write(src.read())
            return True
        except Exception:
            return False

    def validate_keystore(self):
        """Check if keystore file is valid"""
        if not os.path.exists(self.keystore_path):
            return False

        try:
            with open(self.keystore_path, 'r') as f:
                keystore = json.load(f)

            required_fields = ['version', 'salt', 'nonce', 'ciphertext', 'iterations']
            return all(field in keystore for field in required_fields)

        except Exception:
            return False

    def get_wallet_info(self, password):
        """Get basic wallet information without exposing private key"""
        wallet_data = self.unlock_wallet(password)
        if not wallet_data:
            return None

        return {
            'address': wallet_data['address'],
            'public_key': wallet_data['public_key'],
            'created_at': wallet_data.get('created_at', 'unknown')
        }

    def store_transaction_cache(self, tx_hash, tx_data):
        """Cache transaction data in local database"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS wallet_transactions (
                    tx_hash TEXT PRIMARY KEY,
                    tx_data TEXT,
                    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            cursor.execute(
                'INSERT OR REPLACE INTO wallet_transactions (tx_hash, tx_data) VALUES (?, ?)',
                (tx_hash, json.dumps(tx_data))
            )
            conn.commit()

    def get_cached_transactions(self, limit=50):
        """Retrieve cached transaction history"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT tx_hash, tx_data, cached_at
                FROM wallet_transactions
                ORDER BY cached_at DESC
                LIMIT ?
            ''', (limit,))

            results = []
            for row in cursor.fetchall():
                tx_data = json.loads(row[1])
                tx_data['tx_hash'] = row[0]
                tx_data['cached_at'] = row[2]
                results.append(tx_data)

            return results
