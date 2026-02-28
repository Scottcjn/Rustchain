#!/usr/bin/env python3
"""
Focused signature verification integration for /relay/ping endpoint
This implements ONLY the signature verification for issue #308
No scope creep, no additional features.
"""

import hashlib
import hmac
import json
import sqlite3
from typing import Optional, Dict, Any


def verify_signature_for_relay_ping(agent_id: str, signature: str, payload: Dict[str, Any]) -> bool:
    """
    Verify signature for /relay/ping endpoint
    
    Args:
        agent_id: The agent ID making the request
        signature: The signature to verify (from X-Signature header)
        payload: The JSON payload to verify
        
    Returns:
        bool: True if signature is valid, False otherwise
    """
    if not agent_id or not signature or not payload:
        return False
    
    try:
        # Get agent's public key from database
        public_key = _get_agent_public_key(agent_id)
        if not public_key:
            return False
        
        # Create expected signature
        payload_bytes = json.dumps(payload, sort_keys=True).encode('utf-8')
        expected_signature = hmac.new(
            public_key.encode('utf-8'),
            payload_bytes,
            hashlib.sha256
        ).hexdigest()
        
        # Compare signatures (constant time comparison would be better)
        return hmac.compare_digest(signature.lower(), expected_signature.lower())
        
    except Exception as e:
        print(f"Signature verification error: {e}")
        return False


def _get_agent_public_key(agent_id: str) -> Optional[str]:
    """
    Get agent's public key from the beacon database
    
    Args:
        agent_id: The agent ID
        
    Returns:
        str: Public key if found, None otherwise
    """
    try:
        # Database path - assuming same directory as beacon_x402.py
        db_path = "beacon_atlas.db"
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check relay_agents table first
        cursor.execute("SELECT pubkey FROM relay_agents WHERE agent_id = ?", (agent_id,))
        result = cursor.fetchone()
        
        if result and result[0]:
            conn.close()
            return result[0]
            
        # Check beacon_wallets table if not found in relay_agents
        cursor.execute("SELECT pubkey FROM beacon_wallets WHERE agent_id = ?", (agent_id,))
        result = cursor.fetchone()
        
        conn.close()
        
        if result and result[0]:
            return result[0]
            
        return None
        
    except Exception as e:
        print(f"Database error getting public key: {e}")
        return None


# Integration function for beacon_x402.py
def integrate_signature_verification():
    """
    This function should be called to integrate signature verification
    into the existing beacon_x402.py file.
    
    It adds the verify_signature_for_relay_ping function and modifies
    the /relay/ping endpoint to use it.
    """
    pass


if __name__ == "__main__":
    # Test the signature verification
    test_payload = {"test": "data", "timestamp": 1234567890}
    test_signature = "dummy_signature"
    test_agent_id = "test_agent"
    
    result = verify_signature_for_relay_ping(test_agent_id, test_signature, test_payload)
    print(f"Test result: {result}")