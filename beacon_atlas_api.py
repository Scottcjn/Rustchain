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
import base64
import nacl.encoding
import nacl.signing

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

        # Check for allowed domains/patterns
        allowed_patterns = ['rustchain.org', '.rustchain.org']
        if not any(hostname.endswith(pattern) or hostname == pattern.lstrip('.') for pattern in allowed_patterns):
            return False

        return True
    except Exception:
        return False

def verify_admin_key(admin_key):
    """Verify admin key using HMAC"""
    if not admin_key:
        return False
    return hmac.compare_digest(admin_key, ADMIN_KEY)

def verify_ed25519_signature(pubkey_hex, message, signature_hex):
    """Verify Ed25519 signature"""
    try:
        # Decode hex pubkey and signature
        pubkey_bytes = bytes.fromhex(pubkey_hex)
        signature_bytes = bytes.fromhex(signature_hex)

        # Create verifying key
        verify_key = nacl.signing.VerifyKey(pubkey_bytes)

        # Verify signature
        verify_key.verify(message.encode(), signature_bytes)
        return True
    except Exception as e:
        logging.warning(f"Signature verification failed: {e}")
        return False

@app.route('/api/join', methods=['POST', 'OPTIONS'])
def join_beacon():
    """Register a new beacon agent with authentication"""
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        return response

    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid JSON'}), 400

        pubkey = data.get('pubkey', '').strip()
        endpoint = data.get('endpoint', '').strip()
        metadata = data.get('metadata', {})
        admin_key = data.get('admin_key', '')
        signature = data.get('signature', '')

        if not validate_pubkey(pubkey):
            return jsonify({'error': 'Invalid pubkey format'}), 400

        if not validate_endpoint(endpoint):
            return jsonify({'error': 'Invalid or blocked endpoint'}), 400

        # Authentication: either admin key OR valid Ed25519 signature
        auth_valid = False

        if admin_key and verify_admin_key(admin_key):
            auth_valid = True
            logging.info(f"Agent registration via admin key: {pubkey[:16]}...")
        elif signature:
            # Message to sign: "register:{pubkey}:{endpoint}"
            message = f"register:{pubkey}:{endpoint}"
            if verify_ed25519_signature(pubkey, message, signature):
                auth_valid = True
                logging.info(f"Agent registration via signature: {pubkey[:16]}...")

        if not auth_valid:
            return jsonify({'error': 'Authentication required: provide admin_key or valid signature'}), 401

        # Register the agent
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO relay_agents
                (pubkey, endpoint, metadata, last_seen, status)
                VALUES (?, ?, ?, datetime('now'), 'active')
            ''', (pubkey, endpoint, json.dumps(metadata)))
            conn.commit()

        logging.info(f"Registered beacon agent: {pubkey[:16]}... at {endpoint}")

        response = jsonify({
            'status': 'registered',
            'pubkey': pubkey,
            'endpoint': endpoint,
            'timestamp': datetime.utcnow().isoformat()
        })
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response

    except Exception as e:
        logging.error(f"Registration error: {e}")
        return jsonify({'error': 'Registration failed'}), 500

@app.route('/atlas')
def beacon_atlas():
    """Return list of active beacon agents"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT pubkey, endpoint, last_seen, metadata, status
                FROM relay_agents
                WHERE status = 'active'
                ORDER BY last_seen DESC
            ''')
            agents = []
            for row in cursor.fetchall():
                pubkey, endpoint, last_seen, metadata_str, status = row
                try:
                    metadata = json.loads(metadata_str) if metadata_str else {}
                except:
                    metadata = {}

                agents.append({
                    'pubkey': pubkey,
                    'endpoint': endpoint,
                    'last_seen': last_seen,
                    'metadata': metadata,
                    'status': status
                })

        response = jsonify({
            'beacon_agents': agents,
            'count': len(agents),
            'timestamp': datetime.utcnow().isoformat()
        })
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response

    except Exception as e:
        logging.error(f"Atlas error: {e}")
        return jsonify({'error': 'Atlas unavailable'}), 500

@app.route('/status')
def status():
    """Health check endpoint"""
    response = jsonify({
        'service': 'beacon_atlas',
        'status': 'running',
        'timestamp': datetime.utcnow().isoformat()
    })
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response

@app.route('/')
def index():
    """Basic info page"""
    html = '''
    <!DOCTYPE html>
    <html>
    <head><title>Beacon Atlas API</title></head>
    <body>
    <h1>Beacon Atlas API</h1>
    <p>Agent registration and discovery service for Rustchain beacon network.</p>
    <h2>Endpoints:</h2>
    <ul>
        <li><code>POST /api/join</code> - Register beacon agent (requires authentication)</li>
        <li><code>GET /atlas</code> - List active agents</li>
        <li><code>GET /status</code> - Service status</li>
    </ul>
    <h2>Authentication:</h2>
    <p>Registration requires either:</p>
    <ul>
        <li><code>admin_key</code> - Server admin key</li>
        <li><code>signature</code> - Ed25519 signature of "register:{pubkey}:{endpoint}"</li>
    </ul>
    </body>
    </html>
    '''
    return render_template_string(html)

if __name__ == '__main__':
    os.makedirs('/root/beacon', exist_ok=True)
    init_db()
    app.run(host='127.0.0.1', port=8071, debug=False)
