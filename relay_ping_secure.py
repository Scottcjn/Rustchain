// SPDX-License-Identifier: MIT
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
    current_time = int(time.time())
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO agents (agent_id, public_key, relay_token, last_ping, status) VALUES (?, ?, ?, ?, ?)",
            (agent_id, public_key, relay_token, current_time, 'active')
        )
        conn.commit()

def update_agent_ping(agent_id: str, relay_token: str = None):
    """Update existing agent ping timestamp"""
    current_time = int(time.time())
    with sqlite3.connect(DB_PATH) as conn:
        if relay_token:
            conn.execute(
                "UPDATE agents SET last_ping = ?, relay_token = ? WHERE agent_id = ?",
                (current_time, relay_token, agent_id)
            )
        else:
            conn.execute(
                "UPDATE agents SET last_ping = ? WHERE agent_id = ?",
                (current_time, agent_id)
            )
        conn.commit()

@app.route('/relay/ping', methods=['POST'])
def relay_ping_secure():
    """Secure relay ping endpoint with signature verification"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid JSON payload'}), 400

        agent_id = data.get('agent_id')
        signature_b64 = data.get('signature')
        public_key = data.get('public_key')
        relay_token = data.get('relay_token')

        if not agent_id:
            return jsonify({'error': 'agent_id required'}), 400

        # Check if agent exists
        existing_agent = get_agent_by_id(agent_id)

        if existing_agent:
            # Existing agent - require relay_token for heartbeat updates
            if not relay_token:
                return jsonify({'error': 'relay_token required for existing agents'}), 401

            # Verify relay token matches stored token
            if existing_agent['relay_token'] != relay_token:
                return jsonify({'error': 'Invalid relay_token'}), 401

            # Update ping timestamp
            update_agent_ping(agent_id, relay_token)

            return jsonify({
                'status': 'success',
                'message': 'Agent heartbeat updated',
                'agent_id': agent_id,
                'timestamp': int(time.time())
            })

        else:
            # New agent registration - require signature verification
            if not signature_b64 or not public_key:
                return jsonify({'error': 'signature and public_key required for new agents'}), 400

            try:
                signature_bytes = base64.b64decode(signature_b64)
            except Exception:
                return jsonify({'error': 'Invalid signature encoding'}), 400

            # Create message to verify (agent_id + timestamp within 5 min window)
            timestamp = int(time.time())
            message = f"{agent_id}:{timestamp}".encode('utf-8')

            # Verify Ed25519 signature
            if not verify_ed25519_signature(message, signature_bytes, public_key):
                # Try with a small time window for clock drift
                for offset in [-300, -60, 60, 300]:  # 5min, 1min windows
                    test_timestamp = timestamp + offset
                    test_message = f"{agent_id}:{test_timestamp}".encode('utf-8')
                    if verify_ed25519_signature(test_message, signature_bytes, public_key):
                        break
                else:
                    return jsonify({'error': 'Invalid signature'}), 401

            # Register new authenticated agent
            register_new_agent(agent_id, public_key, relay_token)

            return jsonify({
                'status': 'success',
                'message': 'Agent registered successfully',
                'agent_id': agent_id,
                'timestamp': timestamp
            })

    except Exception as e:
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@app.route('/relay/agents', methods=['GET'])
def list_agents():
    """List all registered agents"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            "SELECT agent_id, last_ping, status FROM agents WHERE status = 'active' ORDER BY last_ping DESC"
        )
        agents = []
        for row in cursor.fetchall():
            agents.append({
                'agent_id': row[0],
                'last_ping': row[1],
                'status': row[2]
            })

    return jsonify({'agents': agents, 'count': len(agents)})

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)
