#!/usr/bin/env python3
"""
Focused TOFU Key Management Routes for RustChain
Implements ONLY the HTTP endpoints required for Issue #308:
- Admin endpoint to revoke compromised keys
- Agent endpoint to rotate their own keys

This is a focused implementation that addresses maintainer feedback from PR #386.
"""

import sqlite3
import json
import time
from flask import request, jsonify
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError

# Database path - should match main application
DB_PATH = "./rustchain_v2.db"

def init_tofu_tables():
    """Initialize TOFU key management tables"""
    with sqlite3.connect(DB_PATH) as conn:
        # TOFU keys table - stores first-time public keys
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tofu_keys (
                miner_id TEXT PRIMARY KEY,
                pubkey_hex TEXT NOT NULL,
                first_seen INTEGER NOT NULL,
                last_used INTEGER NOT NULL
            )
        """)
        
        # Revoked keys table - tracks revoked public keys
        conn.execute("""
            CREATE TABLE IF NOT EXISTS revoked_keys (
                pubkey_hex TEXT PRIMARY KEY,
                revoked_by TEXT NOT NULL,  -- 'admin' or miner_id
                reason TEXT,
                revoked_at INTEGER NOT NULL
            )
        """)
        
        conn.commit()

def verify_signature(message: bytes, signature: str, pubkey_hex: str) -> bool:
    """Verify Ed25519 signature"""
    try:
        sig_bytes = bytes.fromhex(signature)
        pubkey_bytes = bytes.fromhex(pubkey_hex)
        verify_key = VerifyKey(pubkey_bytes)
        verify_key.verify(message, sig_bytes)
        return True
    except (BadSignatureError, ValueError, TypeError):
        return False

def is_key_revoked(pubkey_hex: str) -> bool:
    """Check if a public key has been revoked"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            "SELECT 1 FROM revoked_keys WHERE pubkey_hex = ?",
            (pubkey_hex,)
        )
        return cursor.fetchone() is not None

def store_tofu_key(miner_id: str, pubkey_hex: str):
    """Store or update TOFU key for miner"""
    now = int(time.time())
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT INTO tofu_keys (miner_id, pubkey_hex, first_seen, last_used)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(miner_id) DO UPDATE SET
                pubkey_hex = excluded.pubkey_hex,
                last_used = excluded.last_used
        """, (miner_id, pubkey_hex, now, now))
        conn.commit()

def get_miner_pubkey(miner_id: str) -> str:
    """Get the stored TOFU public key for a miner"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            "SELECT pubkey_hex FROM tofu_keys WHERE miner_id = ?",
            (miner_id,)
        )
        row = cursor.fetchone()
        return row[0] if row else None

def revoke_key(pubkey_hex: str, revoked_by: str, reason: str = None):
    """Revoke a public key"""
    now = int(time.time())
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT OR REPLACE INTO revoked_keys (pubkey_hex, revoked_by, reason, revoked_at)
            VALUES (?, ?, ?, ?)
        """, (pubkey_hex, revoked_by, reason, now))
        conn.commit()

# Flask routes
def register_tofu_routes(app):
    """Register TOFU key management routes with the Flask app"""
    
    @app.route('/api/admin/revoke-key', methods=['POST'])
    def admin_revoke_key():
        """Admin endpoint to revoke compromised keys"""
        # Simple admin check - in production this would be more robust
        admin_key = request.headers.get('X-Admin-Key')
        if not admin_key or admin_key != 'your-admin-key-here':
            return jsonify({'error': 'unauthorized'}), 403
        
        data = request.get_json()
        if not data or 'pubkey_hex' not in data:
            return jsonify({'error': 'missing pubkey_hex'}), 400
        
        pubkey_hex = data['pubkey_hex']
        reason = data.get('reason', 'admin revocation')
        
        # Validate pubkey format
        if len(pubkey_hex) != 64:
            return jsonify({'error': 'invalid pubkey_hex format'}), 400
        
        try:
            revoke_key(pubkey_hex, 'admin', reason)
            return jsonify({'success': True, 'message': 'Key revoked successfully'})
        except Exception as e:
            return jsonify({'error': f'revocation failed: {str(e)}'}), 500
    
    @app.route('/api/rotate-key', methods=['POST'])
    def rotate_key():
        """Agent endpoint to rotate their own keys"""
        data = request.get_json()
        if not data or 'miner_id' not in data or 'new_pubkey_hex' not in data or 'signature' not in data:
            return jsonify({'error': 'missing required fields'}), 400
        
        miner_id = data['miner_id']
        new_pubkey_hex = data['new_pubkey_hex']
        signature = data['signature']
        reason = data.get('reason', 'key rotation')
        
        # Validate formats
        if len(new_pubkey_hex) != 64:
            return jsonify({'error': 'invalid new_pubkey_hex format'}), 400
        
        # Get current pubkey for this miner
        current_pubkey = get_miner_pubkey(miner_id)
        if not current_pubkey:
            return jsonify({'error': 'miner not found or no TOFU key established'}), 404
        
        # Verify signature with current key
        message = f"rotate_key:{miner_id}:{new_pubkey_hex}:{int(time.time())}".encode()
        if not verify_signature(message, signature, current_pubkey):
            return jsonify({'error': 'invalid signature'}), 400
        
        # Store new key and revoke old key
        try:
            store_tofu_key(miner_id, new_pubkey_hex)
            revoke_key(current_pubkey, miner_id, reason)
            return jsonify({
                'success': True, 
                'message': 'Key rotated successfully',
                'old_pubkey': current_pubkey,
                'new_pubkey': new_pubkey_hex
            })
        except Exception as e:
            return jsonify({'error': f'rotation failed: {str(e)}'}), 500
    
    @app.route('/api/key-status/<pubkey_hex>', methods=['GET'])
    def key_status(pubkey_hex):
        """Check if a public key is revoked"""
        if len(pubkey_hex) != 64:
            return jsonify({'error': 'invalid pubkey_hex format'}), 400
        
        revoked = is_key_revoked(pubkey_hex)
        return jsonify({'pubkey_hex': pubkey_hex, 'revoked': revoked})
    
    return app