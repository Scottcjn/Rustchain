# SPDX-License-Identifier: MIT

import os
import sqlite3
import json
import time
import hashlib
import hmac
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from pathlib import Path

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Database configuration
DB_PATH = os.environ.get('RELAY_PING_DB', 'relay_ping.db')

def init_db():
    """Initialize the relay ping database"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS agents (
                agent_id TEXT PRIMARY KEY,
                public_key TEXT NOT NULL,
                relay_token TEXT,
                last_ping INTEGER,
                status TEXT DEFAULT 'active',
                metadata TEXT
            );
        ''')

def get_agent_by_id(agent_id):
    """Get agent information by ID"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT agent_id, public_key, relay_token, last_ping, status, metadata FROM agents WHERE agent_id = ?",
            (agent_id,)
        )
        row = cursor.fetchone()
        if row:
            return {
                'agent_id': row[0],
                'public_key': row[1],
                'relay_token': row[2],
                'last_ping': row[3],
                'status': row[4],
                'metadata': row[5]
            }
        return None

@app.route('/api/relay/ping', methods=['POST'])
def relay_ping():
    """Handle secure relay ping requests"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400

        agent_id = data.get('agent_id')
        signature = data.get('signature')
        timestamp = data.get('timestamp')

        if not all([agent_id, signature, timestamp]):
            return jsonify({'error': 'Missing required fields'}), 400

        # Check timestamp freshness (within 5 minutes)
        current_time = int(time.time())
        if abs(current_time - timestamp) > 300:
            return jsonify({'error': 'Timestamp too old or future'}), 401

        # Get agent info
        agent = get_agent_by_id(agent_id)
        if not agent:
            return jsonify({'error': 'Agent not found'}), 404

        # Verify signature would go here in production
        # For now, just update last ping time
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE agents SET last_ping = ? WHERE agent_id = ?",
                (current_time, agent_id)
            )
            conn.commit()

        return jsonify({
            'status': 'success',
            'agent_id': agent_id,
            'timestamp': current_time
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5001)
