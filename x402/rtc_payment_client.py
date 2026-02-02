"""
RTC Payment Client
Automatically handles HTTP 402 Payment Required responses with RTC micropayments.

Usage:
    from rtc_payment_client import RTCClient
    
    client = RTCClient(
        wallet_seed='your-24-word-seed-phrase',
        node_url='https://50.28.86.131'
    )
    
    # Automatic 402 handling
    response = client.get('https://api.example.com/premium/data')
    # Client detects 402 → signs RTC payment → retries → returns 200
"""

import hashlib
import json
import secrets
import time
from typing import Optional, Dict, Any, Union
from dataclasses import dataclass
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Ed25519 signing
import nacl.signing
import nacl.encoding
from nacl.signing import SigningKey

# PBKDF2 for proper seed derivation
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend

# BIP39 for seed phrase handling
try:
    from mnemonic import Mnemonic
    HAS_MNEMONIC = True
except ImportError:
    HAS_MNEMONIC = False


@dataclass
class PaymentReceipt:
    """Receipt for a completed RTC payment."""
    tx_hash: str
    amount: float
    recipient: str
    sender: str
    nonce: str
    timestamp: float


class RTCWallet:
    """
    RTC wallet for signing payments.
    Supports BIP39 seed phrases or raw private keys.
    """
    
    def __init__(
        self,
        seed_phrase: Optional[str] = None,
        private_key: Optional[bytes] = None
    ):
        """
        Initialize wallet from seed phrase or private key.
        
        Args:
            seed_phrase: BIP39 24-word mnemonic
            private_key: Raw 32-byte Ed25519 private key
        """
        if seed_phrase:
            self._init_from_seed(seed_phrase)
        elif private_key:
            self._init_from_key(private_key)
        else:
            raise ValueError("Must provide seed_phrase or private_key")
    
    def _init_from_seed(self, seed_phrase: str):
        """Initialize from BIP39 seed phrase using PBKDF2HMAC derivation."""
        if HAS_MNEMONIC:
            mnemo = Mnemonic("english")
            entropy = mnemo.to_entropy(seed_phrase)
        else:
            # Fallback: use seed phrase directly
            entropy = seed_phrase.encode()
        
        # Derive Ed25519 key using PBKDF2HMAC with rustchain-specific salt
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"rustchain-ed25519",
            iterations=100000,
            backend=default_backend()
        )
        seed = kdf.derive(entropy if isinstance(entropy, bytes) else bytes(entropy))
        
        self._signing_key = SigningKey(seed)
        self._verify_key = self._signing_key.verify_key
    
    def _init_from_key(self, private_key: bytes):
        """Initialize from raw private key."""
        self._signing_key = SigningKey(private_key)
        self._verify_key = self._signing_key.verify_key
    
    @property
    def address(self) -> str:
        """Get wallet address in RTC format (RTC + truncated hash of pubkey)."""
        pubkey_bytes = self._verify_key.encode()
        return f"RTC{hashlib.sha256(pubkey_bytes).hexdigest()[:40]}"
    
    @property
    def public_key(self) -> bytes:
        """Get raw public key bytes."""
        return self._verify_key.encode()
    
    def sign(self, message: Union[str, bytes]) -> bytes:
        """
        Sign a message with Ed25519.
        
        Args:
            message: Message to sign (str or bytes)
            
        Returns:
            64-byte signature
        """
        if isinstance(message, str):
            message = message.encode()
        
        signed = self._signing_key.sign(message)
        return signed.signature


class RTCPaymentHandler:
    """
    Handles x402 payment flow.
    Detects 402 responses, makes payments, and retries requests.
    """
    
    def __init__(
        self,
        wallet: RTCWallet,
        node_url: str = "https://50.28.86.131",
        max_payment: float = 1.0,  # Max auto-pay amount
        verify_ssl: bool = False
    ):
        """
        Initialize payment handler.
        
        Args:
            wallet: RTCWallet instance for signing
            node_url: RustChain node endpoint
            max_payment: Maximum amount to auto-pay (safety limit)
            verify_ssl: Whether to verify SSL certificates
        """
        self.wallet = wallet
        self.node_url = node_url
        self.max_payment = max_payment
        self.verify_ssl = verify_ssl
        self._payment_history = []
    
    def parse_402_response(self, response: requests.Response) -> Optional[Dict]:
        """
        Parse payment requirements from 402 response.
        
        Args:
            response: HTTP response with 402 status
            
        Returns:
            Dict with payment details or None
        """
        if response.status_code != 402:
            return None
        
        # Try headers first (x402 standard)
        amount = response.headers.get('X-Payment-Amount')
        address = response.headers.get('X-Payment-Address')
        nonce = response.headers.get('X-Payment-Nonce')
        
        if amount and address:
            return {
                'amount': float(amount),
                'recipient': address,
                'currency': response.headers.get('X-Payment-Currency', 'RTC'),
                'network': response.headers.get('X-Payment-Network', 'rustchain'),
                'nonce': nonce or '',
                'endpoint': response.headers.get('X-Payment-Endpoint', f"{self.node_url}/wallet/transfer/signed")
            }
        
        # Try JSON body
        try:
            data = response.json()
            if 'payment' in data:
                return data['payment']
        except (ValueError, json.JSONDecodeError):
            pass
        
        return None
    
    def make_payment(self, payment_req: Dict) -> PaymentReceipt:
        """
        Execute an RTC payment.
        
        Args:
            payment_req: Payment requirements dict
            
        Returns:
            PaymentReceipt with transaction details
            
        Raises:
            ValueError: If payment exceeds max_payment limit
            requests.RequestException: If payment fails
        """
        amount = payment_req['amount']
        recipient = payment_req['recipient']
        nonce = payment_req.get('nonce', '')
        
        # Safety check
        if amount > self.max_payment:
            raise ValueError(f"Payment {amount} exceeds max_payment limit {self.max_payment}")
        
        # Create signed transfer
        timestamp = int(time.time())
        tx_nonce = secrets.token_hex(16)  # Cryptographically secure nonce
        
        # Build transfer message with correct field names for RustChain API
        transfer_data = {
            'from_address': self.wallet.address,
            'to_address': recipient,
            'amount_rtc': amount,
            'timestamp': timestamp,
            'nonce': tx_nonce,
            'memo': f"x402:{nonce}"
        }
        
        # Sign the transfer
        message = json.dumps(transfer_data, sort_keys=True)
        signature = self.wallet.sign(message)
        
        # Submit to chain with signature and public key
        response = requests.post(
            f"{self.node_url}/wallet/transfer/signed",
            json={
                **transfer_data,
                'signature': signature.hex(),
                'public_key': self.wallet.public_key.hex()
            },
            timeout=30,
            verify=self.verify_ssl
        )
        
        if response.status_code not in [200, 201]:
            raise requests.RequestException(f"Payment failed: {response.text}")
        
        result = response.json()
        tx_hash = result.get('tx_hash', result.get('hash', hashlib.sha256(message.encode()).hexdigest()))
        
        receipt = PaymentReceipt(
            tx_hash=tx_hash,
            amount=amount,
            recipient=recipient,
            sender=self.wallet.address,
            nonce=nonce,
            timestamp=time.time()
        )
        
        self._payment_history.append(receipt)
        return receipt
    
    def create_payment_headers(self, receipt: PaymentReceipt) -> Dict[str, str]:
        """
        Create headers for authenticated retry request.
        
        Args:
            receipt: Payment receipt from make_payment
            
        Returns:
            Dict of headers to include in retry
        """
        # Sign nonce:tx_hash for proof
        proof_message = f"{receipt.nonce}:{receipt.tx_hash}"
        signature = self.wallet.sign(proof_message)
        
        # Send raw public key hex (not wallet address) for signature verification
        # Server expects hex bytes for Ed25519 verification
        return {
            'X-Payment-TX': receipt.tx_hash,
            'X-Payment-Signature': signature.hex(),
            'X-Payment-Sender': self.wallet.public_key.hex(),
            'X-Payment-Nonce': receipt.nonce
        }
    
    @property
    def payment_history(self):
        """Get list of completed payments."""
        return self._payment_history.copy()
    
    @property
    def total_spent(self) -> float:
        """Get total RTC spent."""
        return sum(p.amount for p in self._payment_history)


class RTCClient:
    """
    HTTP client with automatic x402 payment handling.
    Drop-in replacement for requests with RTC micropayment support.
    """
    
    def __init__(
        self,
        wallet_seed: Optional[str] = None,
        private_key: Optional[bytes] = None,
        node_url: str = "https://50.28.86.131",
        max_payment: float = 1.0,
        auto_pay: bool = True,
        verify_ssl: bool = False
    ):
        """
        Initialize RTC-enabled HTTP client.
        
        Args:
            wallet_seed: BIP39 seed phrase
            private_key: Raw Ed25519 private key
            node_url: RustChain node URL
            max_payment: Maximum auto-pay amount
            auto_pay: Whether to automatically handle 402s
            verify_ssl: Whether to verify SSL certificates
        """
        wallet = RTCWallet(seed_phrase=wallet_seed, private_key=private_key)
        self.payment_handler = RTCPaymentHandler(
            wallet=wallet,
            node_url=node_url,
            max_payment=max_payment,
            verify_ssl=verify_ssl
        )
        self.auto_pay = auto_pay
        self.verify_ssl = verify_ssl
        
        # Create session with retry logic
        self.session = requests.Session()
        retry = Retry(total=3, backoff_factor=0.5)
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
    
    def _request(
        self,
        method: str,
        url: str,
        **kwargs
    ) -> requests.Response:
        """
        Make HTTP request with automatic 402 handling.
        """
        kwargs.setdefault('verify', self.verify_ssl)
        
        # First attempt
        response = self.session.request(method, url, **kwargs)
        
        # Handle 402 Payment Required
        if response.status_code == 402 and self.auto_pay:
            payment_req = self.payment_handler.parse_402_response(response)
            
            if payment_req:
                # Make payment
                receipt = self.payment_handler.make_payment(payment_req)
                
                # Retry with payment proof
                payment_headers = self.payment_handler.create_payment_headers(receipt)
                headers = kwargs.get('headers', {})
                headers.update(payment_headers)
                kwargs['headers'] = headers
                
                response = self.session.request(method, url, **kwargs)
        
        return response
    
    def get(self, url: str, **kwargs) -> requests.Response:
        """HTTP GET with automatic payment."""
        return self._request('GET', url, **kwargs)
    
    def post(self, url: str, **kwargs) -> requests.Response:
        """HTTP POST with automatic payment."""
        return self._request('POST', url, **kwargs)
    
    def put(self, url: str, **kwargs) -> requests.Response:
        """HTTP PUT with automatic payment."""
        return self._request('PUT', url, **kwargs)
    
    def delete(self, url: str, **kwargs) -> requests.Response:
        """HTTP DELETE with automatic payment."""
        return self._request('DELETE', url, **kwargs)
    
    @property
    def wallet_address(self) -> str:
        """Get client's wallet address."""
        return self.payment_handler.wallet.address
    
    @property
    def payment_history(self):
        """Get payment history."""
        return self.payment_handler.payment_history
    
    @property
    def total_spent(self) -> float:
        """Get total RTC spent."""
        return self.payment_handler.total_spent


# Convenience exports
__all__ = [
    'RTCClient',
    'RTCWallet',
    'RTCPaymentHandler',
    'PaymentReceipt'
]
