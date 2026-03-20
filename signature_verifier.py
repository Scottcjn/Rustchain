# SPDX-License-Identifier: MIT

import hashlib
import hmac
import json
from typing import Optional, Dict, Any, Union
try:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

def verify_ed25519_signature(public_key_bytes: bytes, message: bytes, signature: bytes) -> bool:
    """Verify Ed25519 signature against message using public key."""
    if not CRYPTO_AVAILABLE:
        return False

    try:
        public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
        public_key.verify(signature, message)
        return True
    except Exception:
        return False

def extract_public_key_from_agent_id(agent_id: str) -> Optional[bytes]:
    """Extract Ed25519 public key bytes from agent_id format."""
    # Assume agent_id format includes public key as hex
    # This may need adjustment based on actual agent_id format
    try:
        if len(agent_id) >= 64:  # 32 bytes = 64 hex chars
            key_hex = agent_id[:64]
            return bytes.fromhex(key_hex)
    except (ValueError, TypeError):
        pass
    return None

def verify_ping_signature(payload: Dict[str, Any]) -> bool:
    """Verify that a ping payload contains a valid signature from the agent."""
    if not isinstance(payload, dict):
        return False

    agent_id = payload.get('agent_id')
    signature_hex = payload.get('signature')

    if not agent_id or not signature_hex:
        return False

    try:
        signature_bytes = bytes.fromhex(signature_hex)
    except (ValueError, TypeError):
        return False

    public_key_bytes = extract_public_key_from_agent_id(agent_id)
    if not public_key_bytes:
        return False

    # Create canonical message for signing
    message_data = {
        'agent_id': agent_id,
        'timestamp': payload.get('timestamp'),
        'action': 'ping'
    }
    message = json.dumps(message_data, sort_keys=True).encode('utf-8')

    return verify_ed25519_signature(public_key_bytes, message, signature_bytes)

def create_signature_message(agent_id: str, timestamp: int, action: str = 'ping') -> bytes:
    """Create canonical message bytes for signature verification."""
    message_data = {
        'agent_id': agent_id,
        'timestamp': timestamp,
        'action': action
    }
    return json.dumps(message_data, sort_keys=True).encode('utf-8')

def verify_hmac_signature(message: bytes, signature: str, secret_key: str) -> bool:
    """Verify HMAC-SHA256 signature."""
    try:
        expected = hmac.new(
            secret_key.encode('utf-8'),
            message,
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)
    except Exception:
        return False
