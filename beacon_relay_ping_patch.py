# SPDX-License-Identifier: MIT

# Patch for existing beacon relay to add signature verification to /relay/ping endpoint
# This should be integrated into the existing beacon chat server code

import json
import sqlite3
import time
from functools import wraps
from flask import request, jsonify
from beacon_relay_security import require_signature_verification, verify_ping_signature

# Assuming the existing app instance is available
# This would normally be imported from the main beacon relay module
DB_PATH = "beacon_relay.db"  # Use beacon transport DB, not atlas.db

def patch_relay_ping_endpoint(app, db_path=DB_PATH):
    """Apply signature verification patch to existing /relay/ping endpoint"""

    # Store original route handler
    original_ping_handler = None
    for rule in app.url_map.iter_rules():
        if rule.rule == '/relay/ping' and 'POST' in rule.methods:
            endpoint = rule.endpoint
            original_ping_handler = app.view_functions.get(endpoint)
            break

    @app.route('/relay/ping', methods=['POST'])
    @require_signature_verification(db_path)
    def secure_relay_ping():
        """Secured relay ping endpoint with signature verification"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({'error': 'Invalid JSON payload'}), 400

            agent_id = data.get('agent_id')
            timestamp = data.get('timestamp', int(time.time()))

            # Update agent last seen timestamp
            with sqlite3.connect(db_path) as conn:
                conn.execute(
                    "UPDATE beacon_agents SET last_ping = ?, status = 'active' WHERE agent_id = ?",
                    (timestamp, agent_id)
                )
                conn.commit()

            # Call original handler if it exists
            if original_ping_handler:
                return original_ping_handler()
            else:
                # Default response if no original handler
                return jsonify({
                    'status': 'success',
                    'message': 'Ping received and verified',
                    'timestamp': int(time.time()),
                    'agent_id': agent_id
                })

        except Exception as e:
            return jsonify({'error': f'Ping processing error: {str(e)}'}), 500

    return app

def init_beacon_security_tables(db_path=DB_PATH):
    """Initialize security-related tables in beacon database"""
    with sqlite3.connect(db_path) as conn:
        # Ensure beacon_agents table has required columns
        conn.execute('''
            CREATE TABLE IF NOT EXISTS beacon_agents (
                agent_id TEXT PRIMARY KEY,
                public_key TEXT NOT NULL,
                relay_token TEXT,
                last_ping INTEGER,
                status TEXT DEFAULT 'active',
                created_at INTEGER DEFAULT (strftime('%s', 'now')),
                metadata TEXT
            )
        ''')

        # Add public_key column if it doesn't exist
        try:
            conn.execute('ALTER TABLE beacon_agents ADD COLUMN public_key TEXT')
        except sqlite3.OperationalError:
            # Column already exists
            pass

        conn.commit()

# Usage example (would be integrated into main beacon relay module):
# if __name__ == "__main__":
#     from your_beacon_app import app  # Import existing Flask app
#     init_beacon_security_tables()
#     app = patch_relay_ping_endpoint(app)
#     app.run(debug=True)
