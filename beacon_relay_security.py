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
        # Try to extract public key from agent_id for new agents
        public_key_bytes = extract_public_key_from_agent_id(agent_id)
        if not public_key_bytes:
            return False
    else:
        # Use stored public key
        try:
            public_key_bytes = base64.b64decode(agent['public_key'])
        except Exception:
            return False

    # Verify signature
    try:
        signature_bytes = bytes.fromhex(signature_hex)
        message_data = {
            'agent_id': agent_id,
            'timestamp': timestamp
        }
        message_bytes = json.dumps(message_data, sort_keys=True).encode('utf-8')
        return verify_ed25519_signature(message_bytes, signature_bytes, public_key_bytes)
    except Exception:
        return False

def require_signature(db_path: str):
    """Decorator to require valid signature on relay endpoints"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            from flask import request, jsonify

            try:
                data = request.get_json()
                if not data:
                    return jsonify({'error': 'Invalid JSON payload'}), 400

                if not verify_ping_signature(data, db_path):
                    return jsonify({'error': 'Invalid signature'}), 401

                return f(*args, **kwargs)
            except Exception as e:
                return jsonify({'error': 'Signature verification failed'}), 500

        return decorated_function
    return decorator

def update_agent_last_seen(agent_id: str, db_path: str):
    """Update agent's last seen timestamp"""
    current_time = int(time.time())
    with sqlite3.connect(db_path) as conn:
        # First try to update existing agent
        cursor = conn.execute(
            "UPDATE atlas_agents SET last_seen = ? WHERE agent_id = ?",
            (current_time, agent_id)
        )

        # If no rows updated, insert new agent
        if cursor.rowcount == 0:
            public_key_bytes = extract_public_key_from_agent_id(agent_id)
            if public_key_bytes:
                public_key_b64 = base64.b64encode(public_key_bytes).decode('utf-8')
                conn.execute(
                    "INSERT INTO atlas_agents (agent_id, last_seen, public_key, status) VALUES (?, ?, ?, 'active')",
                    (agent_id, current_time, public_key_b64)
                )

        conn.commit()
