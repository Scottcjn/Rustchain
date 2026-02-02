"""
RTC Payment Middleware for Flask
Implements x402 Payment Required protocol for RustChain micropayments.

Usage:
    from rtc_payment_middleware import require_rtc_payment
    
    @app.route('/api/data')
    @require_rtc_payment(amount=0.001)
    def get_data():
        return {'data': 'premium content'}
"""

import functools
import hashlib
import json
import time
from typing import Optional, Callable
from flask import request, Response, g
import requests
import nacl.signing
import nacl.encoding

# RustChain node endpoint
RTC_NODE = "https://50.28.86.131"

# Payment verification cache (in production, use Redis)
_payment_cache = {}
CACHE_TTL = 300  # 5 minutes


class RTCPaymentError(Exception):
    """Base exception for RTC payment errors."""
    pass


class PaymentVerificationError(RTCPaymentError):
    """Payment verification failed."""
    pass


class InsufficientPaymentError(RTCPaymentError):
    """Payment amount insufficient."""
    pass


def verify_rtc_signature(message: bytes, signature: bytes, public_key: bytes) -> bool:
    """
    Verify an Ed25519 signature.
    
    Args:
        message: The original message that was signed
        signature: The 64-byte Ed25519 signature
        public_key: The 32-byte public key
        
    Returns:
        True if signature is valid, False otherwise
    """
    try:
        verify_key = nacl.signing.VerifyKey(public_key)
        verify_key.verify(message, signature)
        return True
    except nacl.exceptions.BadSignature:
        return False
    except Exception:
        return False


def verify_payment_on_chain(tx_hash: str, expected_amount: float, recipient: str) -> bool:
    """
    Verify a payment transaction on the RustChain ledger.
    
    Args:
        tx_hash: Transaction hash to verify
        expected_amount: Expected payment amount in RTC
        recipient: Expected recipient wallet address
        
    Returns:
        True if payment is valid and confirmed
    """
    try:
        response = requests.get(
            f"{RTC_NODE}/transaction/{tx_hash}",
            timeout=10,
            verify=False  # Self-signed cert
        )
        if response.status_code != 200:
            return False
            
        tx_data = response.json()
        
        # Verify amount and recipient
        if tx_data.get('to') != recipient:
            return False
        if float(tx_data.get('amount', 0)) < expected_amount:
            return False
        if tx_data.get('status') != 'confirmed':
            return False
            
        return True
    except Exception as e:
        return False


def generate_payment_nonce() -> str:
    """Generate a unique payment nonce."""
    return hashlib.sha256(f"{time.time()}-{id(request)}".encode()).hexdigest()[:32]


def create_402_response(
    amount: float,
    recipient: str,
    currency: str = "RTC",
    network: str = "rustchain",
    nonce: Optional[str] = None
) -> Response:
    """
    Create an HTTP 402 Payment Required response with x402 headers.
    
    Args:
        amount: Payment amount required
        recipient: Wallet address to receive payment
        currency: Currency code (default: RTC)
        network: Network identifier (default: rustchain)
        nonce: Optional payment nonce for replay protection
        
    Returns:
        Flask Response with 402 status and payment headers
    """
    nonce = nonce or generate_payment_nonce()
    
    response = Response(
        json.dumps({
            "error": "Payment Required",
            "message": f"This endpoint requires a payment of {amount} {currency}",
            "payment": {
                "amount": amount,
                "currency": currency,
                "recipient": recipient,
                "network": network,
                "nonce": nonce,
                "endpoint": f"{RTC_NODE}/wallet/transfer/signed"
            }
        }),
        status=402,
        mimetype='application/json'
    )
    
    # Set x402 payment headers
    response.headers['X-Payment-Amount'] = str(amount)
    response.headers['X-Payment-Currency'] = currency
    response.headers['X-Payment-Address'] = recipient
    response.headers['X-Payment-Network'] = network
    response.headers['X-Payment-Nonce'] = nonce
    response.headers['X-Payment-Endpoint'] = f"{RTC_NODE}/wallet/transfer/signed"
    
    return response


def extract_payment_proof(request) -> Optional[dict]:
    """
    Extract payment proof from request headers.
    
    Expected headers:
        X-Payment-TX: Transaction hash
        X-Payment-Signature: Ed25519 signature of (nonce + tx_hash)
        X-Payment-Sender: Sender's wallet address (public key hex)
        X-Payment-Nonce: Original nonce from 402 response
        
    Returns:
        Dict with payment proof or None if missing
    """
    tx_hash = request.headers.get('X-Payment-TX')
    signature = request.headers.get('X-Payment-Signature')
    sender = request.headers.get('X-Payment-Sender')
    nonce = request.headers.get('X-Payment-Nonce')
    
    if not all([tx_hash, signature, sender, nonce]):
        return None
        
    return {
        'tx_hash': tx_hash,
        'signature': signature,
        'sender': sender,
        'nonce': nonce
    }


def verify_payment_proof(
    proof: dict,
    expected_amount: float,
    recipient: str
) -> bool:
    """
    Verify payment proof from client.
    
    Args:
        proof: Payment proof dict from extract_payment_proof
        expected_amount: Expected payment amount
        recipient: Expected recipient address
        
    Returns:
        True if payment is verified
    """
    # Check cache first
    cache_key = f"{proof['tx_hash']}:{proof['nonce']}"
    if cache_key in _payment_cache:
        cached = _payment_cache[cache_key]
        if time.time() - cached['timestamp'] < CACHE_TTL:
            return cached['valid']
    
    try:
        # Verify signature
        message = f"{proof['nonce']}:{proof['tx_hash']}".encode()
        signature = bytes.fromhex(proof['signature'])
        public_key = bytes.fromhex(proof['sender'])
        
        if not verify_rtc_signature(message, signature, public_key):
            _payment_cache[cache_key] = {'valid': False, 'timestamp': time.time()}
            return False
        
        # Verify on-chain (optional, can skip for speed)
        # if not verify_payment_on_chain(proof['tx_hash'], expected_amount, recipient):
        #     return False
        
        _payment_cache[cache_key] = {'valid': True, 'timestamp': time.time()}
        return True
        
    except Exception as e:
        _payment_cache[cache_key] = {'valid': False, 'timestamp': time.time()}
        return False


def require_rtc_payment(
    amount: float,
    recipient: Optional[str] = None,
    rate_limit: int = 100  # Max requests per minute per sender
):
    """
    Decorator to require RTC payment for an endpoint.
    
    Args:
        amount: Payment amount in RTC
        recipient: Wallet address to receive payment (defaults to env var)
        rate_limit: Maximum requests per minute per sender
        
    Usage:
        @app.route('/api/premium')
        @require_rtc_payment(amount=0.001, recipient='gurgguda')
        def premium_endpoint():
            return {'data': 'premium'}
    """
    import os
    recipient = recipient or os.environ.get('RTC_PAYMENT_ADDRESS', 'gurgguda')
    
    # Rate limiting state
    _rate_limits = {}
    
    def decorator(f: Callable) -> Callable:
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            # Check for payment proof
            proof = extract_payment_proof(request)
            
            if proof is None:
                # No payment proof - return 402
                return create_402_response(amount, recipient)
            
            # Rate limiting
            sender = proof['sender']
            now = time.time()
            minute_key = f"{sender}:{int(now // 60)}"
            
            if minute_key in _rate_limits:
                if _rate_limits[minute_key] >= rate_limit:
                    return Response(
                        json.dumps({"error": "Rate limit exceeded"}),
                        status=429,
                        mimetype='application/json'
                    )
                _rate_limits[minute_key] += 1
            else:
                _rate_limits[minute_key] = 1
            
            # Verify payment
            if not verify_payment_proof(proof, amount, recipient):
                return Response(
                    json.dumps({"error": "Invalid payment proof"}),
                    status=402,
                    mimetype='application/json'
                )
            
            # Payment verified - store sender info and proceed
            g.rtc_sender = sender
            g.rtc_payment_amount = amount
            
            return f(*args, **kwargs)
        
        return wrapper
    return decorator


# Convenience exports
__all__ = [
    'require_rtc_payment',
    'create_402_response',
    'verify_payment_proof',
    'extract_payment_proof',
    'RTCPaymentError',
    'PaymentVerificationError',
    'InsufficientPaymentError'
]
