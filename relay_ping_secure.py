# SPDX-License-Identifier: MIT

import json
import sqlite3
import time
from flask import Flask, request, jsonify
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature
import base64

app = Flask(__name__)
DB_PATH = "atlas.db"

def init_db():
    """Initialize database with required tables"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS agents (
                agent_id TEXT PRIMARY KEY,
                public_key TEXT NOT NULL,
                relay_token TEXT,
                last_ping INTEGER,
                status TEXT DEFAULT 'active',
                metadata TEXT
            )
        ''')
        conn.commit()

def verify_ed25519_signature(message: bytes, signature: bytes, public_key_pem: str) -> bool:
    """Verify Ed25519 signature against message using public key"""
    try:
        public_key_bytes = base64.b64decode(public_key_pem)
        public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
        public_key.verify(signature, message)
        return True
    except (InvalidSignature, ValueError, Exception):
        return False

def get_agent_by_id(agent_id: str):
    """Get agent record from database"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            "SELECT agent_id, public_key, relay_token, last_ping, status FROM agents WHERE agent_id = ?",
            (agent_id,)
        )
        row = cursor.fetchone()
        if row:
            return {
                'agent_id': row[0],
                'public_key': row[1],
                'relay_token': row[2],
                'last_ping': row[3],
                'status': row[4]
            }
    return None

def register_new_agent(agent_id: str, public_key: str, relay_token: str = None):
    """Register new authenticated agent"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO agents (agent_id, public_key, relay_token, last_ping, status) VALUES (?, ?, ?, ?, ?)",
            (agent_id, public_key, relay_token, int(time.time()), 'active')
        )
        conn.commit()

@app.route('/relay/ping', methods=['POST'])
def relay_ping():
    """Secure ping endpoint with signature verification"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid JSON payload'}), 400

        agent_id = data.get('agent_id')
        signature_hex = data.get('signature')
        timestamp = data.get('timestamp')

        if not all([agent_id, signature_hex, timestamp]):
            return jsonify({'error': 'Missing required fields: agent_id, signature, timestamp'}), 400

        # Check timestamp freshness (within 5 minutes)
        current_time = int(time.time())
        if abs(current_time - timestamp) > 300:
            return jsonify({'error': 'Timestamp too old or in future'}), 400

        try:
            signature = bytes.fromhex(signature_hex)
        except ValueError:
            return jsonify({'error': 'Invalid signature format'}), 400

        # Get agent from database
        agent = get_agent_by_id(agent_id)
        if not agent:
            return jsonify({'error': 'Agent not registered'}), 401

        # Create message for verification
        message_data = {
            'agent_id': agent_id,
            'timestamp': timestamp,
            'action': 'ping'
        }
        message = json.dumps(message_data, sort_keys=True).encode('utf-8')

        # Verify signature
        if not verify_ed25519_signature(message, signature, agent['public_key']):
            return jsonify({'error': 'Invalid signature'}), 401

        # Update last ping time
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "UPDATE agents SET last_ping = ? WHERE agent_id = ?",
                (current_time, agent_id)
            )
            conn.commit()

        return jsonify({
            'status': 'success',
            'message': 'Ping verified',
            'timestamp': current_time
        })

    except Exception as e:
        return jsonify({'error': f'Server error: {str(e)}'}), 500

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)
