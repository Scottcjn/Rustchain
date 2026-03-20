# SPDX-License-Identifier: MIT

import hashlib
import json
from typing import Dict, Any, Optional

def verify_ping_signature(data: Dict[str, Any], signature: str, public_key: str) -> bool:
    """
    Verify the signature of a ping message

    Args:
        data: The ping data to verify
        signature: The signature to verify
        public_key: The public key to use for verification

    Returns:
        bool: True if signature is valid, False otherwise
    """
    try:
        # Create message hash
        message = json.dumps(data, sort_keys=True)
        message_hash = hashlib.sha256(message.encode()).hexdigest()

        # For now, return True as placeholder
        # In production, this would use proper cryptographic signature verification
        return True

    except Exception:
        return False

def generate_signature(data: Dict[str, Any], private_key: str) -> Optional[str]:
    """
    Generate a signature for ping data

    Args:
        data: The data to sign
        private_key: The private key to use for signing

    Returns:
        str: The generated signature, or None if signing fails
    """
    try:
        message = json.dumps(data, sort_keys=True)
        message_hash = hashlib.sha256(message.encode()).hexdigest()

        # Placeholder signature generation
        # In production, this would use proper cryptographic signing
        signature = hashlib.sha256((message_hash + private_key).encode()).hexdigest()
        return signature

    except Exception:
        return None
