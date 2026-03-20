# SPDX-License-Identifier: MIT

import json
import sqlite3
import time
import base64
from functools import wraps
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature

def verify_ed25519_signature(message: bytes, signature: bytes, public_key_bytes: bytes) -> bool:
    """Verify Ed25519 signature against message using public key"""
    try:
        public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
        public_key.verify(signature, message)
        return True
    except (InvalidSignature, ValueError, Exception):
        return False

def extract_public_key_from_agent_id(agent_id: str) -> bytes:
    """Extract Ed25519 public key bytes from agent_id format."""
    # Assume agent_id format includes public key as hex
    try:
        if len(agent_id) >= 64:  # 32 bytes = 64 hex chars
            key_hex = agent_id[:64]
            return bytes.fromhex(key_hex)
    except (ValueError, TypeError):
        pass
    return None

def get_agent_by_id(agent_id: str, db_path: str):
    """Get agent record from database"""
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute(
            "SELECT agent_id, public_key, relay_token, last_seen, status FROM atlas_agents WHERE agent_id = ?",
            (agent_id,)
        )
        row = cursor.fetchone()
        if row:
            return {
                'agent_id': row[0],
                'public_key': row[1],
                'relay_token': row[2],
                'last_seen': row[3],
                'status': row[4]
            }
    return None

def verify_ping_signature(data, db_path: str) -> bool:
    """Verify ping signature against agent's public key"""
    agent_id = data.get('agent_id')
    signature_hex = data.get('signature')
    timestamp = data.get('timestamp')

    if not all([agent_id, signature_hex, timestamp]):
        return False

    # Get agent from database
    agent = get_agent_by_id(agent_id, db_path)
    if not agent:
        return False

    try:
        signature_bytes = bytes.fromhex(signature_hex)
        public_key_bytes = base64.b64decode(agent['public_key'])

        # Create canonical message for verification
        message = f"{agent_id}:{timestamp}".encode('utf-8')

        return verify_ed25519_signature(message, signature_bytes, public_key_bytes)
    except (ValueError, TypeError, Exception):
        return False
