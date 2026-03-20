# SPDX-License-Identifier: MIT

import hashlib
import hmac
import json
from typing import Dict, Any, Optional

def verify_ping_signature(data: Dict[str, Any], signature: str, public_key: str) -> bool:
    """Verify signature for relay ping data"""
    try:
        # Create canonical representation of data
        canonical_data = json.dumps(data, sort_keys=True, separators=(',', ':'))

        # Simple HMAC verification for demo
        expected = hmac.new(
            public_key.encode('utf-8'),
            canonical_data.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(signature, expected)
    except Exception:
        return False

def generate_ping_signature(data: Dict[str, Any], private_key: str) -> str:
    """Generate signature for relay ping data"""
    canonical_data = json.dumps(data, sort_keys=True, separators=(',', ':'))
    return hmac.new(
        private_key.encode('utf-8'),
        canonical_data.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
