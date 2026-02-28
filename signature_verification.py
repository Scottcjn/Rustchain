#!/usr/bin/env python3
"""
Focused signature verification for /relay/ping endpoint
Implements minimal, secure signature verification as requested in issue #308
"""

import hashlib
import hmac
from typing import Optional, Dict, Any

def verify_signature(
    message: str,
    signature: str,
    public_key: str,
    algorithm: str = "sha256"
) -> bool:
    """
    Verify message signature using HMAC
    
    Args:
        message: The message to verify
        signature: The signature to verify against
        public_key: The public key or shared secret
        algorithm: Hash algorithm to use (default: sha256)
    
    Returns:
        bool: True if signature is valid, False otherwise
    """
    try:
        # Create HMAC signature
        expected_signature = hmac.new(
            public_key.encode('utf-8'),
            message.encode('utf-8'),
            getattr(hashlib, algorithm)
        ).hexdigest()
        
        # Compare signatures securely
        return hmac.compare_digest(expected_signature, signature)
    
    except Exception:
        return False

def validate_ping_request(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate /relay/ping request with signature verification
    
    Args:
        data: Request data containing message and signature
        
    Returns:
        Dict with validation result and error message if any
    """
    required_fields = ["message", "signature", "public_key"]
    
    # Check required fields
    for field in required_fields:
        if field not in data:
            return {
                "valid": False,
                "error": f"Missing required field: {field}"
            }
    
    # Verify signature
    is_valid = verify_signature(
        data["message"],
        data["signature"],
        data["public_key"]
    )
    
    if not is_valid:
        return {
            "valid": False,
            "error": "Invalid signature"
        }
    
    return {"valid": True, "error": None}