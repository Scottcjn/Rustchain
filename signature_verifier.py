// SPDX-License-Identifier: MIT
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

    message_json = json.dumps(message_data, sort_keys=True, separators=(',', ':'))
    message_bytes = message_json.encode('utf-8')

    return verify_ed25519_signature(public_key_bytes, message_bytes, signature_bytes)

def verify_relay_token(agent_id: str, relay_token: str, secret_key: str) -> bool:
    """Verify relay token for existing agents using HMAC."""
    if not agent_id or not relay_token or not secret_key:
        return False

    try:
        expected_token = hmac.new(
            secret_key.encode('utf-8'),
            agent_id.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(relay_token, expected_token)
    except Exception:
        return False

def validate_agent_ping(payload: Dict[str, Any], secret_key: str, is_existing_agent: bool = False) -> Dict[str, Union[bool, str]]:
    """
    Validate agent ping payload with signature verification.

    Returns dict with 'valid' boolean and optional 'error' message.
    """
    if not isinstance(payload, dict):
        return {'valid': False, 'error': 'Invalid payload format'}

    agent_id = payload.get('agent_id')
    if not agent_id:
        return {'valid': False, 'error': 'Missing agent_id'}

    # For existing agents, check relay token
    if is_existing_agent:
        relay_token = payload.get('relay_token')
        if not relay_token:
            return {'valid': False, 'error': 'Missing relay_token for existing agent'}

        if not verify_relay_token(agent_id, relay_token, secret_key):
            return {'valid': False, 'error': 'Invalid relay_token'}

    # Always require valid signature for new registrations
    if not is_existing_agent:
        if not verify_ping_signature(payload):
            return {'valid': False, 'error': 'Invalid or missing signature'}

    return {'valid': True}
