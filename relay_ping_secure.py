# SPDX-License-Identifier: MIT

import sqlite3
import json
import time
from flask import Flask, request, jsonify

DB_PATH = "relay_ping.db"
app = Flask(__name__)

def get_agent_by_id(agent_id):
    """Get agent information by ID"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM agents WHERE agent_id = ?", (agent_id,))
        result = cursor.fetchone()
        if result:
            return {
                'agent_id': result[0],
                'public_key': result[1],
                'relay_token': result[2],
                'last_ping': result[3],
                'status': result[4],
                'metadata': result[5]
            }
    return None

@app.route('/relay/ping', methods=['POST'])
def relay_ping():
    """Handle relay ping requests"""
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No data provided'}), 400

    agent_id = data.get('agent_id')
    if not agent_id:
        return jsonify({'error': 'Missing agent_id'}), 400

    # Check for signature
    signature = data.get('signature')
    if not signature:
        return jsonify({'error': 'Missing signature'}), 401

    # Verify agent exists
    agent = get_agent_by_id(agent_id)
    if not agent:
        return jsonify({'error': 'Agent not found'}), 404

    return jsonify({'status': 'success', 'message': 'Ping received'})

if __name__ == '__main__':
    app.run(debug=True)
