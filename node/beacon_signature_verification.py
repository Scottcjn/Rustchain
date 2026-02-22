"""
Beacon Atlas Signature Verification Module
Implements Ed25519 signature verification for /relay/ping endpoint using TOFU stored public keys.

This module provides the core verification logic that should be integrated into the 
Beacon Atlas Flask application's /relay/ping endpoint.

Usage:
    from beacon_signature_verification import verify_relay_ping_signature
    
    # In your /relay/ping endpoint handler
    if agent_has_stored_pubkey(agent_id):
        if not verify_relay_ping_signature(agent_id, request_data, signature):
            return jsonify({"error": "Invalid signature"}), 401
"""

import base64
import json
import sqlite3
from typing import Optional, Dict, Any

# Import existing crypto utilities from beacon_skill
try:
    from beacon_skill.crypto import verify_ed25519_signature
    HAVE_BEACON_SKILL = True
except ImportError:
    HAVE_BEACON_SKILL = False

# Fallback Ed25519 verification using pynacl (same as TOFU implementation)
try:
    from nacl.signing import VerifyKey
    from nacl.exceptions import BadSignatureError
    HAVE_NACL = True
except ImportError:
    HAVE_NACL = False


def get_db() -> sqlite3.Connection:
    """
    Get database connection to beacon_atlas.db.
    This should be replaced with the actual database connection method used by Beacon Atlas.
    """
    db_path = "/root/rustchain/node/beacon_atlas.db"
    return sqlite3.connect(db_path)


def tofu_get_key_info(conn: sqlite3.Connection, agent_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve TOFU key information for an agent from the relay_agents table.
    
    Args:
        conn: Database connection
        agent_id: Agent identifier
        
    Returns:
        Dictionary containing key info or None if not found
    """
    try:
        cursor = conn.execute(
            "SELECT pubkey_hex, revoked FROM relay_agents WHERE agent_id = ?",
            (agent_id,)
        )
        row = cursor.fetchone()
        if row:
            return {
                "pubkey_hex": row[0],
                "revoked": bool(row[1])
            }
        return None
    except sqlite3.OperationalError:
        # Table might not exist yet
        return None


def verify_ed25519_fallback(pubkey_hex: str, message: bytes, signature_b64: str) -> bool:
    """
    Fallback Ed25519 signature verification using pynacl.
    
    Args:
        pubkey_hex: Public key in hexadecimal format
        message: Message bytes to verify
        signature_b64: Base64-encoded signature
        
    Returns:
        True if signature is valid, False otherwise
    """
    if not HAVE_NACL:
        return False
        
    try:
        # Convert hex pubkey to bytes
        pubkey_bytes = bytes.fromhex(pubkey_hex)
        verify_key = VerifyKey(pubkey_bytes)
        
        # Decode base64 signature
        signature_bytes = base64.b64decode(signature_b64)
        
        # Verify signature
        verify_key.verify(message, signature_bytes)
        return True
    except (BadSignatureError, ValueError, TypeError):
        return False


def verify_relay_ping_signature(agent_id: str, payload: Dict[str, Any], signature: str) -> bool:
    """
    Verify Ed25519 signature for /relay/ping endpoint using TOFU stored public key.
    
    This function should be called by the Beacon Atlas /relay/ping endpoint handler
    when signature verification is required.
    
    Args:
        agent_id: Relay agent ID from the ping request
        payload: Ping payload data (excluding signature field)
        signature: Base64-encoded Ed25519 signature of the payload
        
    Returns:
        bool: True if signature is valid and agent has a valid stored pubkey,
              False otherwise (including cases where agent has no stored pubkey)
    """
    # Get database connection
    try:
        conn = get_db()
    except Exception:
        return False
    
    try:
        # Retrieve stored public key for this agent
        key_info = tofu_get_key_info(conn, agent_id)
        
        # If no key info or key is revoked, verification fails
        if not key_info or key_info.get('revoked', False):
            return False
            
        pubkey_hex = key_info['pubkey_hex']
        if not pubkey_hex:
            return False
        
        # Prepare message for verification (JSON payload without signature)
        # Ensure consistent JSON serialization
        message_dict = payload.copy()
        # Remove signature field if present to avoid circular dependency
        if 'signature' in message_dict:
            del message_dict['signature']
            
        message_json = json.dumps(message_dict, sort_keys=True, separators=(',', ':'))
        message_bytes = message_json.encode('utf-8')
        
        # Verify signature using available crypto library
        if HAVE_BEACON_SKILL:
            try:
                return verify_ed25519_signature(pubkey_hex, message_bytes, signature)
            except Exception:
                # Fall back to pynacl if beacon_skill fails
                pass
                
        # Use fallback verification
        return verify_ed25519_fallback(pubkey_hex, message_bytes, signature)
        
    finally:
        conn.close()


def agent_has_stored_pubkey(agent_id: str) -> bool:
    """
    Check if an agent has a stored public key in the TOFU database.
    This function helps determine whether signature verification should be enforced.
    
    Args:
        agent_id: Agent identifier
        
    Returns:
        True if agent has a stored pubkey, False otherwise
    """
    try:
        conn = get_db()
        key_info = tofu_get_key_info(conn, agent_id)
        conn.close()
        return key_info is not None and key_info.get('pubkey_hex') is not None
    except Exception:
        return False


# Integration example for Beacon Atlas /relay/ping endpoint
def integrate_with_beacon_atlas_example():
    """
    Example of how to integrate this module with the Beacon Atlas Flask application.
    
    In your Beacon Atlas application (likely in a file like beacon_atlas.py or similar):
    
    ```python
    from beacon_signature_verification import verify_relay_ping_signature, agent_has_stored_pubkey
    from flask import request, jsonify
    
    @app.route('/relay/ping', methods=['POST'])
    def relay_ping():
        data = request.get_json()
        agent_id = data.get('agent_id')
        
        # Backward compatibility: only enforce signature verification for agents with stored pubkeys
        if agent_has_stored_pubkey(agent_id):
            signature = data.get('signature')
            if not signature:
                return jsonify({"error": "Signature required"}), 401
                
            # Verify signature
            if not verify_relay_ping_signature(agent_id, data, signature):
                return jsonify({"error": "Invalid signature"}), 401
        
        # Process ping as usual
        # ... rest of ping handling logic ...
        
        return jsonify({"status": "ok"})
    ```
    """
    pass