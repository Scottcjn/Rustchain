# SPDX-License-Identifier: MIT

from flask import Flask, request, jsonify, render_template_string
import sqlite3
import json
import logging
import os
import hashlib
import hmac
import ipaddress
from urllib.parse import urlparse
from datetime import datetime

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

DB_PATH = '/root/beacon/beacon_atlas.db'
ADMIN_KEY = os.environ.get('BEACON_ADMIN_KEY', 'change-me-in-production')

def init_db():
    """Initialize the beacon atlas database"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS relay_agents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pubkey TEXT UNIQUE NOT NULL,
                endpoint TEXT NOT NULL,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()

def validate_pubkey(pubkey):
    """Basic pubkey validation"""
    if not pubkey or not isinstance(pubkey, str):
        return False
    if len(pubkey) < 32 or len(pubkey) > 128:
        return False
    return True

def is_private_ip(ip_str):
    """Check if IP is private, link-local, or loopback"""
    try:
        ip = ipaddress.ip_address(ip_str)
        return ip.is_private or ip.is_link_local or ip.is_loopback or ip.is_multicast
    except ValueError:
        return True  # Invalid IP, treat as suspicious

def validate_endpoint(endpoint):
    """Enhanced endpoint validation to prevent SSRF"""
    if not endpoint or not isinstance(endpoint, str):
        return False

    if not (endpoint.startswith('http://') or endpoint.startswith('https://')):
        return False

    try:
        parsed = urlparse(endpoint)
        hostname = parsed.hostname

        if not hostname:
            return False

        # Block private/internal IPs
        if is_private_ip(hostname):
            return False

        # Additional checks for common internal hostnames
        blocked_hosts = ['localhost', 'metadata.google.internal', 'metadata']
        if hostname.lower() in blocked_hosts:
            return False

        return True
    except Exception:
        return False

def verify_admin_auth(request):
    """Verify admin key authentication"""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return False

    token = auth_header[7:]  # Remove 'Bearer ' prefix
    return hmac.compare_digest(token, ADMIN_KEY)

@app.route('/api/join', methods=['POST'])
def join_beacon():
    """Agent registration endpoint with admin authentication"""
    try:
        # Require admin authentication
        if not verify_admin_auth(request):
            return jsonify({'error': 'Admin authentication required'}), 401

        data = request.get_json()
        if not data:
            return jsonify({'error': 'JSON data required'}), 400

        pubkey = data.get('pubkey')
        endpoint = data.get('endpoint')
        metadata = data.get('metadata', {})

        if not validate_pubkey(pubkey):
            return jsonify({'error': 'Invalid pubkey format'}), 400

        if not validate_endpoint(endpoint):
            return jsonify({'error': 'Invalid endpoint format or blocked address'}), 400

        # Store in database
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO relay_agents
                (pubkey, endpoint, metadata, last_seen, status)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP, 'active')
            ''', (pubkey, endpoint, json.dumps(metadata)))
            conn.commit()

        logging.info(f"Agent registered: {pubkey[:8]}... -> {endpoint}")

        return jsonify({
            'success': True,
            'message': 'Agent registered successfully',
            'pubkey': pubkey,
            'endpoint': endpoint
        })

    except Exception as e:
        logging.error(f"Registration error: {e}")
        return jsonify({'error': 'Registration failed'}), 500

@app.route('/api/agents', methods=['GET'])
def list_agents():
    """List all registered agents"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT pubkey, endpoint, last_seen, status, metadata
                FROM relay_agents
                WHERE status = 'active'
                ORDER BY last_seen DESC
            ''')

            agents = []
            for row in cursor.fetchall():
                agents.append({
                    'pubkey': row[0],
                    'endpoint': row[1],
                    'last_seen': row[2],
                    'status': row[3],
                    'metadata': json.loads(row[4]) if row[4] else {}
                })

            return jsonify({
                'success': True,
                'agents': agents,
                'count': len(agents)
            })

    except Exception as e:
        logging.error(f"List agents error: {e}")
        return jsonify({'error': 'Failed to list agents'}), 500

@app.route('/atlas', methods=['GET'])
def beacon_atlas():
    """Beacon atlas endpoint"""
    html_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Beacon Atlas</title>
        <style>
            body { font-family: monospace; background: #1a1a1a; color: #0ff; margin: 20px; }
            .agent { margin: 10px 0; padding: 10px; border: 1px solid #333; }
            .pubkey { color: #ff0; }
            .endpoint { color: #0f0; }
        </style>
    </head>
    <body>
        <h1>Beacon Atlas - Active Relay Agents</h1>
        <div id="agents"></div>
        <script>
            fetch('/api/agents')
                .then(r => r.json())
                .then(data => {
                    const div = document.getElementById('agents');
                    if (data.success) {
                        div.innerHTML = data.agents.map(a =>
                            `<div class="agent">
                                <div class="pubkey">PubKey: ${a.pubkey}</div>
                                <div class="endpoint">Endpoint: ${a.endpoint}</div>
                                <div>Last Seen: ${a.last_seen}</div>
                            </div>`
                        ).join('');
                    } else {
                        div.innerHTML = 'Error loading agents';
                    }
                });
        </script>
    </body>
    </html>
    """
    return render_template_string(html_template)

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.utcnow().isoformat()})

if __name__ == '__main__':
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    init_db()
    app.run(host='0.0.0.0', port=8071, debug=False)
