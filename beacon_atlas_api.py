# SPDX-License-Identifier: MIT

from flask import Flask, request, jsonify, render_template_string
import sqlite3
import json
import os
from datetime import datetime
import re

app = Flask(__name__)

# Database path
DB_PATH = '/root/beacon/beacon_atlas.db'

def init_db():
    """Initialize the database with relay_agents table"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS relay_agents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT UNIQUE NOT NULL,
                pubkey_hex TEXT NOT NULL,
                endpoint TEXT,
                location TEXT,
                version TEXT,
                last_seen INTEGER,
                metadata TEXT,
                created_at INTEGER DEFAULT (strftime('%s', 'now'))
            )
        ''')
        conn.commit()

def validate_pubkey_hex(pubkey):
    """Validate hex public key format"""
    if not isinstance(pubkey, str):
        return False
    if len(pubkey) not in [64, 66]:  # 32 bytes = 64 hex chars, optionally with 0x prefix
        return False
    # Remove 0x prefix if present
    clean_pubkey = pubkey[2:] if pubkey.startswith('0x') else pubkey
    return bool(re.match(r'^[a-fA-F0-9]{64}$', clean_pubkey))

@app.route('/api/join', methods=['POST'])
def join_beacon():
    """Register or update an agent in the beacon network"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400

        # Extract required fields
        pubkey_hex = data.get('pubkey_hex') or data.get('pubkey')
        agent_id = data.get('agent_id')

        if not pubkey_hex:
            return jsonify({'error': 'pubkey_hex is required'}), 400

        if not validate_pubkey_hex(pubkey_hex):
            return jsonify({'error': 'Invalid pubkey_hex format'}), 400

        # Clean pubkey (remove 0x if present)
        clean_pubkey = pubkey_hex[2:] if pubkey_hex.startswith('0x') else pubkey_hex

        # Generate agent_id if not provided
        if not agent_id:
            agent_id = f"agent_{clean_pubkey[:12]}"

        # Extract optional fields
        endpoint = data.get('endpoint', '')
        location = data.get('location', '')
        version = data.get('version', '1.0')
        metadata = json.dumps(data.get('metadata', {}))

        current_time = int(datetime.now().timestamp())

        # Upsert agent (insert or update on conflict)
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO relay_agents
                (agent_id, pubkey_hex, endpoint, location, version, last_seen, metadata, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?,
                    COALESCE((SELECT created_at FROM relay_agents WHERE agent_id = ?), ?))
            ''', (agent_id, clean_pubkey, endpoint, location, version,
                  current_time, metadata, agent_id, current_time))
            conn.commit()

        return jsonify({
            'status': 'success',
            'agent_id': agent_id,
            'message': 'Agent registered successfully'
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/agents', methods=['GET'])
def list_agents():
    """List all registered beacon agents"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('''
                SELECT agent_id, pubkey_hex, endpoint, location, version,
                       last_seen, metadata, created_at
                FROM relay_agents
                ORDER BY last_seen DESC, created_at DESC
            ''')
            rows = cursor.fetchall()

        agents = []
        for row in rows:
            agent_data = {
                'agent_id': row['agent_id'],
                'pubkey_hex': row['pubkey_hex'],
                'endpoint': row['endpoint'],
                'location': row['location'],
                'version': row['version'],
                'last_seen': row['last_seen'],
                'created_at': row['created_at']
            }

            # Parse metadata if available
            if row['metadata']:
                try:
                    agent_data['metadata'] = json.loads(row['metadata'])
                except:
                    agent_data['metadata'] = {}

            agents.append(agent_data)

        return jsonify({
            'status': 'success',
            'total_agents': len(agents),
            'agents': agents
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/beacon/atlas', methods=['GET'])
def beacon_atlas_web():
    """Web interface for beacon atlas"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('''
                SELECT COUNT(*) as total FROM relay_agents
            ''')
            total_count = cursor.fetchone()['total']

            cursor = conn.execute('''
                SELECT agent_id, pubkey_hex, endpoint, location, version, last_seen
                FROM relay_agents
                ORDER BY last_seen DESC
                LIMIT 20
            ''')
            recent_agents = cursor.fetchall()

        html_template = '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Beacon Atlas - Rustchain Network</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; background: #1a1a1a; color: #fff; }
                .header { background: #2d4a22; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
                .stats { display: flex; gap: 20px; margin-bottom: 20px; }
                .stat-box { background: #333; padding: 15px; border-radius: 6px; flex: 1; }
                .agent-list { background: #333; padding: 20px; border-radius: 8px; }
                .agent { border-bottom: 1px solid #555; padding: 10px 0; }
                .agent:last-child { border-bottom: none; }
                .pubkey { font-family: monospace; color: #4a9eff; }
                .endpoint { color: #90ee90; }
                h1 { margin: 0; color: #90ee90; }
                h2 { color: #ccc; }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🗺️ Beacon Atlas</h1>
                <p>Rustchain Network Relay Agent Registry</p>
            </div>

            <div class="stats">
                <div class="stat-box">
                    <h3>Total Agents</h3>
                    <div style="font-size: 2em; color: #90ee90;">{{ total_count }}</div>
                </div>
                <div class="stat-box">
                    <h3>Network Status</h3>
                    <div style="color: #90ee90;">🟢 Online</div>
                </div>
            </div>

            <div class="agent-list">
                <h2>Recent Agents (Last 20)</h2>
                {% for agent in agents %}
                <div class="agent">
                    <strong>{{ agent.agent_id }}</strong><br>
                    <span class="pubkey">{{ agent.pubkey_hex[:16] }}...{{ agent.pubkey_hex[-8:] }}</span><br>
                    {% if agent.endpoint %}
                    <span class="endpoint">{{ agent.endpoint }}</span><br>
                    {% endif %}
                    {% if agent.location %}
                    📍 {{ agent.location }}
                    {% endif %}
                    <span style="color: #888; font-size: 0.9em;">v{{ agent.version }}</span>
                </div>
                {% endfor %}
            </div>

            <div style="margin-top: 30px; padding: 15px; background: #2d2d2d; border-radius: 6px;">
                <h3>API Endpoints</h3>
                <p><code>GET /api/agents</code> - List all agents</p>
                <p><code>POST /api/join</code> - Register new agent</p>
            </div>
        </body>
        </html>
        '''

        return render_template_string(html_template,
                                    total_count=total_count,
                                    agents=recent_agents)

    except Exception as e:
        return f"Error loading beacon atlas: {str(e)}", 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'service': 'beacon_atlas'}), 200

if __name__ == '__main__':
    # Ensure database directory exists
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    init_db()

    # Run on port 8071 as specified in the issue
    app.run(host='0.0.0.0', port=8071, debug=False)
