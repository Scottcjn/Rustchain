"""
RustChain Cryptography Module
Handles wallet generation, key management, and transaction signing
"""

import os
import json
import hashlib
import secrets
from typing import Optional, Tuple
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
from mnemonic import Mnemonic
from nacl.signing import SigningKey, VerifyKey
from nacl.encoding import HexEncoder


class RustChainWallet:
    """RustChain wallet with BIP39 seed phrases and Ed25519 signatures"""
    
    def __init__(self, seed_phrase: Optional[str] = None):
        """
        Initialize wallet from seed phrase or generate new one
        
        Args:
            seed_phrase: Optional 24-word BIP39 seed phrase
        """
        self.mnemo = Mnemonic("english")
        
        if seed_phrase:
            if not self.mnemo.check(seed_phrase):
                raise ValueError("Invalid seed phrase")
            self.seed_phrase = seed_phrase
        else:
            # Generate new 24-word seed phrase (256 bits of entropy)
            self.seed_phrase = self.mnemo.generate(strength=256)
        
        # Derive Ed25519 key from seed
        self.signing_key = self._derive_signing_key(self.seed_phrase)
        self.verify_key = self.signing_key.verify_key
        
        # Generate RustChain address
        self.address = self._generate_address(self.verify_key)
    
    def _derive_signing_key(self, seed_phrase: str) -> SigningKey:
        """Derive Ed25519 signing key from BIP39 seed phrase"""
        # Convert mnemonic to seed (512 bits)
        seed = self.mnemo.to_seed(seed_phrase, passphrase="")
        
        # Use first 32 bytes as Ed25519 private key
        private_key_bytes = seed[:32]
        
        return SigningKey(private_key_bytes)
    
    def _generate_address(self, verify_key: VerifyKey) -> str:
        """Generate RustChain address from public key"""
        # Address format: RTC + first 40 chars of SHA256(public_key)
        pubkey_hex = verify_key.encode(encoder=HexEncoder).decode('utf-8')
        pubkey_hash = hashlib.sha256(bytes.fromhex(pubkey_hex)).hexdigest()
        return f"RTC{pubkey_hash[:40]}"
    
    def sign_transaction(self, tx_data: dict) -> dict:
        """
        Sign a transaction
        
        Args:
            tx_data: Transaction dictionary with from_addr, to_addr, amount, timestamp
            
        Returns:
            Signed transaction with signature field
        """
        # Canonical JSON for signing (sorted keys, no whitespace)
        canonical_tx = json.dumps(tx_data, sort_keys=True, separators=(',', ':'))
        tx_bytes = canonical_tx.encode('utf-8')
        
        # Sign with Ed25519
        signature = self.signing_key.sign(tx_bytes)
        sig_hex = signature.signature.hex()
        
        # Return transaction with signature
        signed_tx = tx_data.copy()
        signed_tx['signature'] = sig_hex
        signed_tx['public_key'] = self.verify_key.encode(encoder=HexEncoder).decode('utf-8')
        
        return signed_tx
    
    def get_public_key_hex(self) -> str:
        """Get public key as hex string"""
        return self.verify_key.encode(encoder=HexEncoder).decode('utf-8')
    
    def get_private_key_hex(self) -> str:
        """Get private key as hex string (sensitive!)"""
        return self.signing_key.encode(encoder=HexEncoder).decode('utf-8')


class WalletKeystore:
    """Encrypted wallet keystore manager"""
    
    PBKDF2_ITERATIONS = 100000
    
    @staticmethod
    def encrypt_keystore(wallet: RustChainWallet, password: str, wallet_name: str) -> dict:
        """
        Encrypt wallet data into keystore format
        
        Args:
            wallet: RustChainWallet instance
            password: Encryption password
            wallet_name: Wallet identifier
            
        Returns:
            Keystore dictionary
        """
        # Derive encryption key from password
        salt = secrets.token_bytes(32)
        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=WalletKeystore.PBKDF2_ITERATIONS
        )
        key = kdf.derive(password.encode('utf-8'))
        
        # Prepare wallet data
        wallet_data = {
            'seed_phrase': wallet.seed_phrase,
            'address': wallet.address,
            'public_key': wallet.get_public_key_hex(),
            'private_key': wallet.get_private_key_hex()
        }
        
        # Encrypt with AES-256-GCM
        aesgcm = AESGCM(key)
        nonce = secrets.token_bytes(12)
        plaintext = json.dumps(wallet_data).encode('utf-8')
        ciphertext = aesgcm.encrypt(nonce, plaintext, None)
        
        # Build keystore
        keystore = {
            'version': 1,
            'wallet_name': wallet_name,
            'address': wallet.address,
            'crypto': {
                'cipher': 'aes-256-gcm',
                'kdf': 'pbkdf2',
                'kdf_params': {
                    'iterations': WalletKeystore.PBKDF2_ITERATIONS,
                    'salt': salt.hex()
                },
                'nonce': nonce.hex(),
                'ciphertext': ciphertext.hex()
            }
        }
        
        return keystore
    
    @staticmethod
    def decrypt_keystore(keystore: dict, password: str) -> RustChainWallet:
        """
        Decrypt keystore and restore wallet
        
        Args:
            keystore: Keystore dictionary
            password: Decryption password
            
        Returns:
            RustChainWallet instance
        """
        crypto = keystore['crypto']
        
        # Derive decryption key
        salt = bytes.fromhex(crypto['kdf_params']['salt'])
        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=crypto['kdf_params']['iterations']
        )
        key = kdf.derive(password.encode('utf-8'))
        
        # Decrypt
        aesgcm = AESGCM(key)
        nonce = bytes.fromhex(crypto['nonce'])
        ciphertext = bytes.fromhex(crypto['ciphertext'])
        
        try:
            plaintext = aesgcm.decrypt(nonce, ciphertext, None)
            wallet_data = json.loads(plaintext.decode('utf-8'))
        except Exception:
            raise ValueError("Invalid password or corrupted keystore")
        
        # Restore wallet from seed phrase
        wallet = RustChainWallet(seed_phrase=wallet_data['seed_phrase'])
        
        return wallet
    
    @staticmethod
    def save_keystore(keystore: dict, directory: Path) -> Path:
        """Save keystore to file"""
        directory.mkdir(parents=True, exist_ok=True)
        filename = f"{keystore['wallet_name']}.json"
        filepath = directory / filename
        
        with open(filepath, 'w') as f:
            json.dump(keystore, f, indent=2)
        
        # Set restrictive permissions
        filepath.chmod(0o600)
        
        return filepath
    
    @staticmethod
    def load_keystore(filepath: Path) -> dict:
        """Load keystore from file"""
        with open(filepath, 'r') as f:
            return json.load(f)


def verify_transaction(tx_data: dict) -> bool:
    """
    Verify transaction signature
    
    Args:
        tx_data: Signed transaction with signature and public_key fields
        
    Returns:
        True if signature is valid
    """
    if 'signature' not in tx_data or 'public_key' not in tx_data:
        return False
    
    # Extract signature and public key
    sig_hex = tx_data['signature']
    pubkey_hex = tx_data['public_key']
    
    # Reconstruct canonical tx for verification
    tx_copy = {k: v for k, v in tx_data.items() if k not in ['signature', 'public_key']}
    canonical_tx = json.dumps(tx_copy, sort_keys=True, separators=(',', ':'))
    tx_bytes = canonical_tx.encode('utf-8')
    
    # Verify signature
    try:
        verify_key = VerifyKey(bytes.fromhex(pubkey_hex))
        verify_key.verify(tx_bytes, bytes.fromhex(sig_hex))
        return True
    except Exception:
        return False
