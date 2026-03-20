# SPDX-License-Identifier: MIT

"""
Signature verification utilities for relay ping security.
Provides cryptographic verification functions for agent authentication.
"""

import hashlib
import hmac
import base64
from typing import Optional, Dict, Any


def verify_ping_signature(payload: Dict[str, Any], signature: str, public_key: str) -> bool:
    """
    Verify the signature of a ping payload using the agent's public key.

    Args:
        payload: The ping payload data
        signature: Base64 encoded signature to verify
        public_key: Agent's public key for verification

    Returns:
        bool: True if signature is valid, False otherwise
    """
    try:
        # Create canonical string representation of payload
        canonical_payload = _create_canonical_payload(payload)

        # Decode the signature
        decoded_signature = base64.b64decode(signature)

        # Verify using HMAC-SHA256 (simplified approach)
        expected_signature = hmac.new(
            public_key.encode('utf-8'),
            canonical_payload.encode('utf-8'),
            hashlib.sha256
        ).digest()

        return hmac.compare_digest(decoded_signature, expected_signature)

    except Exception as e:
        print(f"Signature verification error: {e}")
        return False


def _create_canonical_payload(payload: Dict[str, Any]) -> str:
    """
    Create a canonical string representation of the payload for signing.

    Args:
        payload: Dictionary payload to canonicalize

    Returns:
        str: Canonical string representation
    """
    # Sort keys and create deterministic string
    sorted_items = sorted(payload.items())
    canonical_parts = []

    for key, value in sorted_items:
        canonical_parts.append(f"{key}={value}")

    return "&".join(canonical_parts)


def generate_signature(payload: Dict[str, Any], private_key: str) -> str:
    """
    Generate a signature for a payload using a private key.

    Args:
        payload: The payload data to sign
        private_key: Private key for signing

    Returns:
        str: Base64 encoded signature
    """
    canonical_payload = _create_canonical_payload(payload)

    signature = hmac.new(
        private_key.encode('utf-8'),
        canonical_payload.encode('utf-8'),
        hashlib.sha256
    ).digest()

    return base64.b64encode(signature).decode('utf-8')


def verify_timestamp(timestamp: int, max_age: int = 300) -> bool:
    """
    Verify that a timestamp is within the acceptable age range.

    Args:
        timestamp: Unix timestamp to verify
        max_age: Maximum age in seconds (default 5 minutes)

    Returns:
        bool: True if timestamp is valid, False otherwise
    """
    import time
    current_time = int(time.time())
    age = current_time - timestamp

    return 0 <= age <= max_age
