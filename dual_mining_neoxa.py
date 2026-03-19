// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import os
import sqlite3
import subprocess
import socket
import json
import time
from datetime import datetime
from flask import Flask, request, render_template_string, jsonify

app = Flask(__name__)

DB_PATH = 'rustchain_mining.db'
NEOX_RPC_HOST = 'localhost'
NEOX_RPC_PORT = 8788
NEOX_RPC_USER = 'user'
NEOX_RPC_PASS = 'pass'

def init_neoxa_db():
    """Initialize the database table for Neoxa mining sessions"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS neoxa_mining_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                miner_type TEXT NOT NULL,
                process_id INTEGER,
                status TEXT NOT NULL,
                hashrate REAL DEFAULT 0,
                shares_accepted INTEGER DEFAULT 0,
                shares_rejected INTEGER DEFAULT 0,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ended_at TIMESTAMP,
                rpc_status TEXT DEFAULT 'unknown'
            )
        ''')
        conn.commit()

def check_neox_rpc():
    """Check if Neoxa RPC is accessible"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3)
        result = s.connect_ex((NEOX_RPC_HOST, NEOX_RPC_PORT))
        s.close()
        
        if result == 0:
            # Try to make an actual RPC call
            try:
                rpc_data = {
                    "jsonrpc": "1.0",
                    "id": "neoxa_check",
                    "method": "getblockchaininfo",
                    "params": []
                }
                
                import http.client
                import base64
                
                conn = http.client.HTTPConnection(NEOX_RPC_HOST, NEOX_RPC_PORT)
                auth_string = f"{NEOX_RPC_USER}:{NEOX_RPC_PASS}"
                auth_bytes = base64.b64encode(auth_string.encode()).decode()
                
                headers = {
                    'Content-Type': 'application/json',
                    'Authorization': f'Basic {auth_bytes}'
                }
                
                conn.request('POST', '/', json.dumps(rpc_data), headers)
                response = conn.getresponse()
                data = response.read()
                conn.close()
                
                if response.status == 200:
                    result = json.loads(data.decode())
                    if 'result' in result:
                        return {'status': 'connected', 'blocks': result['result'].get('blocks', 0)}
                    
            except Exception as e:
                return {'status': 'port_open', 'error': str(e)}
                
        return {'status': 'offline'}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

def detect_mining_processes():
    """Detect running mining processes for Neoxa"""
    processes = []
    target_processes = ['neoxad', 't-rex', 'gminer', 'nbminer']
    
    try:
        if os.name == 'nt':  # Windows
            cmd = 'tasklist /FO CSV'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            lines = result.stdout.strip().split('\n')[1:]  # Skip header
            
            for line in lines:
                if line:
                    parts = [p.strip('"') for p in line.split('","')]
                    if len(parts) >= 2:
                        process_name = parts[0].lower()
                        pid = parts[1]
                        
                        for target in target_processes:
                            if target in process_name:
                                processes.append({
                                    'name': parts[0],
                                    'pid': int(pid),
                                    'type': target,
                                    'cpu': parts[4] if len(parts) > 4 else '0'
                                })
        else:  # Linux/Unix
            result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
            lines = result.stdout.strip().split('\n')[1:]  # Skip header
            
            for line in lines:
                parts = line.split()
                if len(parts) >= 11:
                    process_name = ' '.join(parts[10:]).lower()
                    pid = parts[1]
                    cpu = parts[2]
                    
                    for target in target_processes:
                        if target in process_name:
                            processes.append({
                                'name': parts[10],
                                'pid': int(pid),
                                'type': target,
                                'cpu': cpu
                            })
                            
    except Exception as e:
        print(f"Error detecting processes: {e}")
        
    return processes

def log_mining_session(session_id, miner_type, process_id, status, hashrate=0):
    """Log mining session to database"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        rpc_status = check_neox_rpc()['status']
        
        cursor.execute('''
            INSERT INTO neoxa_mining_sessions 
            (session_id, miner_type, process_id, status, hashrate, rpc_status)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (session_id, miner_type, process_id, status, hashrate, rpc_status))
        conn.commit()

@app.route('/neoxa/status')
def neoxa_status():
    """Get current Neoxa mining status"""
    rpc_status = check_neox_rpc()
    mining_processes = detect_mining_processes()
    
    # Get recent mining sessions
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM neoxa_mining_sessions 
            ORDER BY started_at DESC LIMIT 10
        ''')
        sessions = cursor.fetchall()
    
    total_hashrate = sum(float(p.get('cpu', 0)) for p in mining_processes)
    
    status_html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Neoxa Mining Status</title>
        <style>
            body { font-family: monospace; background: #1a1a1a; color: #00ff00; margin: 20px; }
            .status-box { border: 1px solid #00ff00; padding: 15px; margin: 10px 0; }
            .online { color: #00ff00; }
            .offline { color: #ff0000; }
            table { border-collapse: collapse; width: 100%; margin: 10px 0; }
            th, td { border: 1px solid #00ff00; padding: 8px; text-align: left; }
            th { background-color: #333; }
        </style>
    </head>
    <body>
        <h1>🔗 Neoxa (NEOX) Dual Mining Status</h1>
        
        <div class="status-box">
            <h2>RPC Connection</h2>
            <p>Status: <span class="{{ 'online' if rpc_status['status'] == 'connected' else 'offline' }}">
                {{ rpc_status['status'].upper() }}
            </span></p>
            {% if rpc_status.get('blocks') %}
            <p>Current Block: {{ rpc_status['blocks'] }}</p>
            {% endif %}
            <p>Endpoint: {{ rpc_host }}:{{ rpc_port }}</p>
        </div>
        
        <div class="status-box">
            <h2>Active Mining Processes</h2>
            <p>Detected: {{ mining_processes|length }} processes</p>
            {% if mining_processes %}
            <table>
                <tr><th>Process</th><th>PID</th><th>Type</th><th>CPU %</th></tr>
                {% for proc in mining_processes %}
                <tr>
                    <td>{{ proc.name }}</td>
                    <td>{{ proc.pid }}</td>
                    <td>{{ proc.type }}</td>
                    <td>{{ proc.cpu }}%</td>
                </tr>
                {% endfor %}
            </table>
            {% else %}
            <p class="offline">No mining processes detected</p>
            {% endif %}
        </div>
        
        <div class="status-box">
            <h2>Recent Sessions</h2>
            {% if sessions %}
            <table>
                <tr><th>Session ID</th><th>Miner</th><th>Status</th><th>Started</th><th>RPC Status</th></tr>
                {% for session in sessions %}
                <tr>
                    <td>{{ session[1][:8] }}...</td>
                    <td>{{ session[2] }}</td>
                    <td>{{ session[4] }}</td>
                    <td>{{ session[8] }}</td>
                    <td>{{ session[10] }}</td>
                </tr>
                {% endfor %}
            </table>
            {% else %}
            <p>No recent sessions</p>
            {% endif %}
        </div>
        
        <div class="status-box">
            <h2>Mining Statistics</h2>
            <p>Total Estimated Hashrate: {{ "%.2f"|format(total_hashrate) }} MH/s</p>
            <p>Algorithm: KawPow</p>
            <p>Last Update: {{ current_time }}</p>
        </div>
    </body>
    </html>
    '''
    
    return render_template_string(status_html, 
        rpc_status=rpc_status,
        mining_processes=mining_processes,
        sessions=sessions,
        rpc_host=NEOX_RPC_HOST,
        rpc_port=NEOX_RPC_PORT,
        total_hashrate=total_hashrate,
        current_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    )

@app.route('/neoxa/api/status')
def neoxa_api_status():
    """JSON API endpoint for Neoxa mining status"""
    rpc_status = check_neox_rpc()
    mining_processes = detect_mining_processes()
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM neoxa_mining_sessions WHERE status="active"')
        active_sessions = cursor.fetchone()[0]
    
    return jsonify({
        'rpc': rpc_status,
        'mining_processes': mining_processes,
        'active_sessions': active_sessions,
        'algorithm': 'KawPow',
        'coin': 'NEOX',
        'timestamp': int(time.time())
    })

@app.route('/neoxa/start/<miner_type>')
def start_neoxa_mining(miner_type):
    """Start Neoxa mining session"""
    if miner_type not in ['trex', 'gminer', 'nbminer', 'neoxad']:
        return jsonify({'error': 'Invalid miner type'}), 400
    
    session_id = f"neox_{miner_type}_{int(time.time())}"
    
    # Check if miner process is already running
    processes = detect_mining_processes()
    existing = [p for p in processes if p['type'] == miner_type.replace('trex', 't-rex')]
    
    if existing:
        log_mining_session(session_id, miner_type, existing[0]['pid'], 'active')
        return jsonify({
            'message': f'{miner_type} already running',
            'session_id': session_id,
            'pid': existing[0]['pid']
        })
    
    # In a real implementation, you would start the miner process here
    # For now, just log the attempt
    log_mining_session(session_id, miner_type, 0, 'starting')
    
    return jsonify({
        'message': f'Starting {miner_type} mining session',
        'session_id': session_id,
        'note': 'Process starting logic would be implemented here'
    })

@app.route('/neoxa/check')
def check_neoxa():
    """Quick check endpoint"""
    rpc = check_neox_rpc()
    processes = len(detect_mining_processes())
    
    status = "🟢 ONLINE" if rpc['status'] == 'connected' else "🔴 OFFLINE"
    
    return f'''
    <h2>Neoxa Quick Check</h2>
    <p>RPC: {status}</p>
    <p>Mining Processes: {processes}</p>
    <p>Timestamp: {datetime.now()}</p>
    <a href="/neoxa/status">Full Status</a>
    '''

if __name__ == '__main__':
    init_neoxa_db()
    print("🔗 Neoxa dual-mining integration initialized")
    print(f"📊 Status available at: http://localhost:5000/neoxa/status")
    print(f"🔌 RPC checking: {NEOX_RPC_HOST}:{NEOX_RPC_PORT}")
    
    app.run(debug=True, host='0.0.0.0', port=5000)