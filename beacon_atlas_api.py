// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

from flask import Flask, request, jsonify, render_template_string
import sqlite3
import json
import logging
import os
from datetime import datetime

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

DB_PATH = '/root/beacon/beacon_atlas.db'

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

def validate_endpoint(endpoint):
    """Basic endpoint validation"""
    if not endpoint or not isinstance(endpoint, str):
        return False
    if not (endpoint.startswith('http://') or endpoint.startswith('https://')):
        return False
    return True

@app.route('/api/join', methods=['POST'])
def join_beacon():
    """Agent registration endpoint"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'JSON data required'}), 400
        
        pubkey = data.get('pubkey')
        endpoint = data.get('endpoint')
        metadata = data.get('metadata', {})
        
        if not validate_pubkey(pubkey):
            return jsonify({'error': 'Invalid pubkey format'}), 400
        
        if not validate_endpoint(endpoint):
            return jsonify({'error': 'Invalid endpoint format'}), 400
        
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # Check for existing agent
            cursor.execute('SELECT id FROM relay_agents WHERE pubkey = ?', (pubkey,))
            existing = cursor.fetchone()
            
            if existing:
                # Update existing agent
                cursor.execute('''
                    UPDATE relay_agents 
                    SET endpoint = ?, metadata = ?, last_seen = CURRENT_TIMESTAMP, status = 'active'
                    WHERE pubkey = ?
                ''', (endpoint, json.dumps(metadata), pubkey))
                
                logging.info(f"Updated existing agent: {pubkey[:16]}...")
                return jsonify({
                    'status': 'updated',
                    'message': 'Agent registration updated',
                    'pubkey': pubkey
                })
            else:
                # Insert new agent
                cursor.execute('''
                    INSERT INTO relay_agents (pubkey, endpoint, metadata, status)
                    VALUES (?, ?, ?, 'active')
                ''', (pubkey, endpoint, json.dumps(metadata)))
                
                conn.commit()
                
                logging.info(f"Registered new agent: {pubkey[:16]}...")
                return jsonify({
                    'status': 'registered',
                    'message': 'Agent successfully registered',
                    'pubkey': pubkey
                })
                
    except sqlite3.IntegrityError as e:
        logging.error(f"Database integrity error: {e}")
        return jsonify({'error': 'Registration failed - duplicate entry'}), 409
    except Exception as e:
        logging.error(f"Registration error: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/agents', methods=['GET'])
def list_agents():
    """List all registered agents"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT pubkey, endpoint, last_seen, metadata, status, created_at 
                FROM relay_agents 
                ORDER BY last_seen DESC
            ''')
            
            rows = cursor.fetchall()
            
            agents = []
            for row in rows:
                try:
                    metadata = json.loads(row[3]) if row[3] else {}
                except json.JSONDecodeError:
                    metadata = {}
                
                agents.append({
                    'pubkey': row[0],
                    'endpoint': row[1],
                    'last_seen': row[2],
                    'metadata': metadata,
                    'status': row[4],
                    'created_at': row[5]
                })
            
            return jsonify({
                'agents': agents,
                'count': len(agents),
                'timestamp': datetime.utcnow().isoformat()
            })
            
    except Exception as e:
        logging.error(f"Error listing agents: {e}")
        return jsonify({'error': 'Failed to retrieve agents'}), 500

@app.route('/beacon/atlas', methods=['GET'])
def beacon_atlas():
    """Web interface for beacon atlas"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT pubkey, endpoint, last_seen, status 
                FROM relay_agents 
                ORDER BY last_seen DESC
            ''')
            
            agents = cursor.fetchall()
            
            html_template = '''
            <!DOCTYPE html>
            <html>
            <head>
                <title>Beacon Atlas - Agent Registry</title>
                <style>
                    body { font-family: monospace; margin: 40px; background: #0a0a0a; color: #00ff00; }
                    table { border-collapse: collapse; width: 100%; margin-top: 20px; }
                    th, td { border: 1px solid #333; padding: 8px; text-align: left; }
                    th { background: #1a1a1a; }
                    .status-active { color: #00ff00; }
                    .status-inactive { color: #ff6600; }
                    .header { color: #00ccff; margin-bottom: 20px; }
                </style>
            </head>
            <body>
                <h1 class="header">🚀 Beacon Atlas - Agent Registry</h1>
                <p>Total Agents: {{ agent_count }}</p>
                
                <table>
                    <tr>
                        <th>Public Key</th>
                        <th>Endpoint</th>
                        <th>Last Seen</th>
                        <th>Status</th>
                    </tr>
                    {% for agent in agents %}
                    <tr>
                        <td>{{ agent[0][:16] }}...</td>
                        <td>{{ agent[1] }}</td>
                        <td>{{ agent[2] }}</td>
                        <td class="status-{{ agent[3] }}">{{ agent[3] }}</td>
                    </tr>
                    {% endfor %}
                </table>
                
                <div style="margin-top: 30px; color: #666;">
                    <p>API Endpoints:</p>
                    <ul>
                        <li>POST /api/join - Register new agent</li>
                        <li>GET /api/agents - List all agents (JSON)</li>
                    </ul>
                </div>
            </body>
            </html>
            '''
            
            return render_template_string(html_template, 
                                        agents=agents, 
                                        agent_count=len(agents))
            
    except Exception as e:
        logging.error(f"Error rendering atlas page: {e}")
        return f"Error loading beacon atlas: {str(e)}", 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'beacon_atlas_api',
        'timestamp': datetime.utcnow().isoformat()
    })

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=8071, debug=False)