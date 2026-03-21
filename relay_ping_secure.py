# SPDX-License-Identifier: MIT

import sqlite3
import json
import time
import hashlib
import os
from flask import Flask, request, jsonify, render_template_string
from contextlib import contextmanager
from typing import Dict, List, Optional, Any

app = Flask(__name__)
DB_PATH = "rustchain.db"

@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    """Initialize relay ping security database"""
    with get_db() as conn:
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

def get_agent_by_id(agent_id: str) -> Optional[Dict]:
    """Get agent information by ID"""
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT * FROM agents WHERE agent_id = ?",
            (agent_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

@app.route('/relay/ping', methods=['POST'])
def relay_ping():
    """Secure relay ping endpoint"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400

        agent_id = data.get('agent_id')
        signature = data.get('signature')
        timestamp = data.get('timestamp')

        if not all([agent_id, signature, timestamp]):
            return jsonify({"error": "Missing required fields"}), 400

        # Verify signature
        agent = get_agent_by_id(agent_id)
        if not agent:
            return jsonify({"error": "Agent not found"}), 404

        # Update last ping
        with get_db() as conn:
            conn.execute(
                "UPDATE agents SET last_ping = ? WHERE agent_id = ?",
                (int(time.time()), agent_id)
            )
            conn.commit()

        return jsonify({"status": "success", "message": "Ping received"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
