# SPDX-License-Identifier: MIT

"""
Secure Relay Ping Service
Handles authenticated ping requests from agents with signature verification.
"""

import os
import json
import sqlite3
import time
import hashlib
import hmac
from flask import Flask, request, jsonify, render_template_string
from typing import Dict, Optional, Tuple

app = Flask(__name__)

# Configuration
DB_PATH = os.getenv("RELAY_DB_PATH", "relay_ping.db")
SECRET_KEY = os.getenv("RELAY_SECRET_KEY", "default-secret-key")
MAX_PING_AGE = int(os.getenv("MAX_PING_AGE", "300"))  # 5 minutes

# Initialize database
def init_database():
    """Initialize SQLite database for relay ping tracking"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS agents (
                agent_id TEXT PRIMARY KEY,
                public_key TEXT NOT NULL,
                relay_token TEXT,
                last_ping INTEGER,
                status TEXT DEFAULT 'active',
                metadata TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ping_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT,
                timestamp INTEGER,
                status TEXT,
                ip_address TEXT,
                user_agent TEXT
            )
        """)
        conn.commit()


def get_agent_by_id(agent_id: str) -> Optional[Dict]:
    """Retrieve agent information by ID"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        result = conn.execute(
            "SELECT * FROM agents WHERE agent_id = ?",
            (agent_id,)
        ).fetchone()
        return dict(result) if result else None


def log_ping_attempt(agent_id: str, status: str, ip_address: str, user_agent: str):
    """Log ping attempt for monitoring and debugging"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO ping_logs (agent_id, timestamp, status, ip_address, user_agent) VALUES (?, ?, ?, ?, ?)",
            (agent_id, int(time.time()), status, ip_address, user_agent)
        )
        conn.commit()


def update_agent_ping(agent_id: str, timestamp: int):
    """Update last ping timestamp for agent"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE agents SET last_ping = ? WHERE agent_id = ?",
            (timestamp, agent_id)
        )
        conn.commit()


def verify_ping_signature(payload: str, signature: str, public_key: str) -> bool:
    """Verify HMAC signature for ping payload"""
    try:
        expected_signature = hmac.new(
            public_key.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected_signature, signature)
    except Exception:
        return False


@app.route('/ping', methods=['POST'])
def handle_ping():
    """Handle secure ping requests from agents"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON payload"}), 400

        agent_id = data.get('agent_id')
        timestamp = data.get('timestamp')
        signature = request.headers.get('X-Signature')

        if not all([agent_id, timestamp, signature]):
            return jsonify({"error": "Missing required fields"}), 400

        # Check timestamp freshness
        current_time = int(time.time())
        if abs(current_time - timestamp) > MAX_PING_AGE:
            log_ping_attempt(agent_id, 'expired', request.remote_addr, request.headers.get('User-Agent', ''))
            return jsonify({"error": "Timestamp too old"}), 400

        # Get agent info
        agent = get_agent_by_id(agent_id)
        if not agent:
            log_ping_attempt(agent_id, 'unknown_agent', request.remote_addr, request.headers.get('User-Agent', ''))
            return jsonify({"error": "Unknown agent"}), 404

        # Verify signature
        payload = json.dumps(data, sort_keys=True)
        if not verify_ping_signature(payload, signature, agent['public_key']):
            log_ping_attempt(agent_id, 'invalid_signature', request.remote_addr, request.headers.get('User-Agent', ''))
            return jsonify({"error": "Invalid signature"}), 403

        # Update ping timestamp
        update_agent_ping(agent_id, timestamp)
        log_ping_attempt(agent_id, 'success', request.remote_addr, request.headers.get('User-Agent', ''))

        return jsonify({
            "status": "success",
            "agent_id": agent_id,
            "timestamp": current_time,
            "next_ping": current_time + 60  # Suggest next ping in 60 seconds
        })

    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500


@app.route('/agents', methods=['GET'])
def list_agents():
    """List all registered agents and their status"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        agents = conn.execute(
            "SELECT agent_id, last_ping, status FROM agents ORDER BY last_ping DESC"
        ).fetchall()

        current_time = int(time.time())
        agent_list = []

        for agent in agents:
            last_ping = agent['last_ping'] or 0
            time_since_ping = current_time - last_ping

            agent_list.append({
                "agent_id": agent['agent_id'],
                "last_ping": last_ping,
                "time_since_ping": time_since_ping,
                "status": "online" if time_since_ping < 120 else "offline",
                "configured_status": agent['status']
            })

        return jsonify({"agents": agent_list})


@app.route('/dashboard', methods=['GET'])
def dashboard():
    """Simple HTML dashboard for monitoring agents"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        agents = conn.execute(
            "SELECT agent_id, last_ping, status FROM agents ORDER BY last_ping DESC"
        ).fetchall()

        recent_pings = conn.execute(
            "SELECT * FROM ping_logs ORDER BY timestamp DESC LIMIT 20"
        ).fetchall()

    template = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Relay Ping Dashboard</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            table { border-collapse: collapse; width: 100%; margin: 20px 0; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
            th { background-color: #f2f2f2; }
            .online { color: green; }
            .offline { color: red; }
            .success { color: green; }
            .error { color: red; }
        </style>
    </head>
    <body>
        <h1>Relay Ping Dashboard</h1>

        <h2>Agents Status</h2>
        <table>
            <tr>
                <th>Agent ID</th>
                <th>Last Ping</th>
                <th>Status</th>
            </tr>
            {% for agent in agents %}
            <tr>
                <td>{{ agent.agent_id }}</td>
                <td>{{ agent.last_ping_human if agent.last_ping else 'Never' }}</td>
                <td class="{{ agent.status_class }}">{{ agent.status_text }}</td>
            </tr>
            {% endfor %}
        </table>

        <h2>Recent Ping Logs</h2>
        <table>
            <tr>
                <th>Timestamp</th>
                <th>Agent ID</th>
                <th>Status</th>
                <th>IP Address</th>
            </tr>
            {% for ping in recent_pings %}
            <tr>
                <td>{{ ping.timestamp_human }}</td>
                <td>{{ ping.agent_id }}</td>
                <td class="{{ ping.status_class }}">{{ ping.status }}</td>
                <td>{{ ping.ip_address }}</td>
            </tr>
            {% endfor %}
        </table>
    </body>
    </html>
    """

    # Format data for template
    current_time = int(time.time())
    formatted_agents = []

    for agent in agents:
        last_ping = agent['last_ping'] or 0
        time_since_ping = current_time - last_ping

        formatted_agents.append({
            'agent_id': agent['agent_id'],
            'last_ping_human': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(last_ping)) if last_ping else 'Never',
            'status_class': 'online' if time_since_ping < 120 else 'offline',
            'status_text': f"Online ({time_since_ping}s ago)" if time_since_ping < 120 else f"Offline ({time_since_ping}s ago)"
        })

    formatted_pings = []
    for ping in recent_pings:
        formatted_pings.append({
            'timestamp_human': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(ping['timestamp'])),
            'agent_id': ping['agent_id'],
            'status': ping['status'],
            'status_class': 'success' if ping['status'] == 'success' else 'error',
            'ip_address': ping['ip_address']
        })

    return render_template_string(template, agents=formatted_agents, recent_pings=formatted_pings)


if __name__ == '__main__':
    init_database()
    app.run(host='0.0.0.0', port=5000, debug=False)
