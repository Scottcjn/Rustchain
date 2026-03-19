// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import sqlite3
import json
import time
import hashlib
from datetime import datetime, timedelta
from decimal import Decimal
from flask import Flask, request, jsonify, render_template_string
import os

DB_PATH = "rustchain.db"

class BridgeAPI:
    def __init__(self):
        self.setup_database()
    
    def setup_database(self):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS bridge_locks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lock_id TEXT UNIQUE NOT NULL,
                    from_chain TEXT NOT NULL,
                    to_chain TEXT NOT NULL,
                    from_address TEXT NOT NULL,
                    to_address TEXT NOT NULL,
                    amount TEXT NOT NULL,
                    token_type TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL,
                    release_tx_hash TEXT,
                    metadata TEXT
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS bridge_ledger (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lock_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    chain TEXT NOT NULL,
                    tx_hash TEXT,
                    amount TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    block_height INTEGER,
                    gas_used INTEGER,
                    FOREIGN KEY (lock_id) REFERENCES bridge_locks (lock_id)
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS chain_configs (
                    chain_name TEXT PRIMARY KEY,
                    rpc_endpoint TEXT NOT NULL,
                    contract_address TEXT,
                    token_decimals INTEGER DEFAULT 9,
                    min_lock_amount TEXT DEFAULT '1.0',
                    max_lock_amount TEXT DEFAULT '10000.0',
                    lock_timeout_hours INTEGER DEFAULT 24,
                    is_active INTEGER DEFAULT 1
                )
            ''')
            
            # Initialize default chain configs
            chains = [
                ('rustchain', 'http://localhost:8000', None, 9, '1.0', '10000.0', 24, 1),
                ('solana', 'https://api.devnet.solana.com', None, 9, '1.0', '10000.0', 24, 1),
                ('base', 'https://goerli.base.org', None, 18, '1.0', '10000.0', 24, 1)
            ]
            
            for chain_data in chains:
                conn.execute('''
                    INSERT OR IGNORE INTO chain_configs 
                    (chain_name, rpc_endpoint, contract_address, token_decimals, 
                     min_lock_amount, max_lock_amount, lock_timeout_hours, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', chain_data)
            
            conn.commit()

    def generate_lock_id(self, from_chain, to_chain, from_addr, amount):
        timestamp = str(int(time.time()))
        data = f"{from_chain}:{to_chain}:{from_addr}:{amount}:{timestamp}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def create_lock(self, from_chain, to_chain, from_address, to_address, amount, token_type='wRTC'):
        lock_id = self.generate_lock_id(from_chain, to_chain, from_address, amount)
        created_at = time.time()
        expires_at = created_at + (24 * 3600)  # 24 hours
        
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''
                INSERT INTO bridge_locks 
                (lock_id, from_chain, to_chain, from_address, to_address, 
                 amount, token_type, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (lock_id, from_chain, to_chain, from_address, to_address, 
                  amount, token_type, created_at, expires_at))
            
            # Log the lock creation
            self.add_ledger_entry(lock_id, 'lock_created', from_chain, None, amount)
            
            conn.commit()
            
        return lock_id

    def get_lock(self, lock_id):
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('''
                SELECT * FROM bridge_locks WHERE lock_id = ?
            ''', (lock_id,))
            
            row = cursor.fetchone()
            return dict(row) if row else None

    def update_lock_status(self, lock_id, status, release_tx_hash=None):
        with sqlite3.connect(DB_PATH) as conn:
            if release_tx_hash:
                conn.execute('''
                    UPDATE bridge_locks 
                    SET status = ?, release_tx_hash = ?
                    WHERE lock_id = ?
                ''', (status, release_tx_hash, lock_id))
            else:
                conn.execute('''
                    UPDATE bridge_locks 
                    SET status = ?
                    WHERE lock_id = ?
                ''', (status, lock_id))
            
            conn.commit()

    def add_ledger_entry(self, lock_id, action, chain, tx_hash, amount, block_height=None, gas_used=None):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''
                INSERT INTO bridge_ledger 
                (lock_id, action, chain, tx_hash, amount, timestamp, block_height, gas_used)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (lock_id, action, chain, tx_hash, amount, time.time(), block_height, gas_used))
            
            conn.commit()

    def get_lock_history(self, lock_id):
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('''
                SELECT * FROM bridge_ledger 
                WHERE lock_id = ? 
                ORDER BY timestamp DESC
            ''', (lock_id,))
            
            return [dict(row) for row in cursor.fetchall()]

    def get_pending_locks(self, chain=None):
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            
            if chain:
                cursor = conn.execute('''
                    SELECT * FROM bridge_locks 
                    WHERE status = 'pending' AND (from_chain = ? OR to_chain = ?)
                    ORDER BY created_at DESC
                ''', (chain, chain))
            else:
                cursor = conn.execute('''
                    SELECT * FROM bridge_locks 
                    WHERE status = 'pending'
                    ORDER BY created_at DESC
                ''')
            
            return [dict(row) for row in cursor.fetchall()]

    def cleanup_expired_locks(self):
        current_time = time.time()
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute('''
                SELECT lock_id FROM bridge_locks 
                WHERE status = 'pending' AND expires_at < ?
            ''', (current_time,))
            
            expired_locks = [row[0] for row in cursor.fetchall()]
            
            for lock_id in expired_locks:
                conn.execute('''
                    UPDATE bridge_locks 
                    SET status = 'expired' 
                    WHERE lock_id = ?
                ''', (lock_id,))
                
                self.add_ledger_entry(lock_id, 'expired', 'system', None, '0')
            
            conn.commit()
            return len(expired_locks)

bridge_api = BridgeAPI()

app = Flask(__name__)

@app.route('/bridge/lock', methods=['POST'])
def create_lock_endpoint():
    data = request.get_json()
    
    required_fields = ['from_chain', 'to_chain', 'from_address', 'to_address', 'amount']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 400
    
    try:
        lock_id = bridge_api.create_lock(
            data['from_chain'],
            data['to_chain'], 
            data['from_address'],
            data['to_address'],
            data['amount'],
            data.get('token_type', 'wRTC')
        )
        
        return jsonify({
            'success': True,
            'lock_id': lock_id,
            'message': 'Lock created successfully'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/bridge/release', methods=['POST'])
def release_lock_endpoint():
    data = request.get_json()
    
    if 'lock_id' not in data:
        return jsonify({'error': 'Missing lock_id'}), 400
    
    lock_id = data['lock_id']
    tx_hash = data.get('tx_hash')
    
    lock = bridge_api.get_lock(lock_id)
    if not lock:
        return jsonify({'error': 'Lock not found'}), 404
    
    if lock['status'] != 'pending':
        return jsonify({'error': f'Lock status is {lock["status"]}, cannot release'}), 400
    
    try:
        bridge_api.update_lock_status(lock_id, 'released', tx_hash)
        bridge_api.add_ledger_entry(lock_id, 'released', lock['to_chain'], tx_hash, lock['amount'])
        
        return jsonify({
            'success': True,
            'message': 'Lock released successfully'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/bridge/status/<lock_id>')
def get_lock_status(lock_id):
    lock = bridge_api.get_lock(lock_id)
    if not lock:
        return jsonify({'error': 'Lock not found'}), 404
    
    history = bridge_api.get_lock_history(lock_id)
    
    return jsonify({
        'lock': lock,
        'history': history
    })

@app.route('/bridge/pending')
def get_pending_locks():
    chain = request.args.get('chain')
    locks = bridge_api.get_pending_locks(chain)
    
    return jsonify({
        'pending_locks': locks,
        'count': len(locks)
    })

@app.route('/bridge/cleanup', methods=['POST'])
def cleanup_expired():
    cleaned_count = bridge_api.cleanup_expired_locks()
    
    return jsonify({
        'success': True,
        'expired_locks_cleaned': cleaned_count
    })

@app.route('/bridge/dashboard')
def bridge_dashboard():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        
        # Get recent locks
        recent_cursor = conn.execute('''
            SELECT * FROM bridge_locks 
            ORDER BY created_at DESC 
            LIMIT 20
        ''')
        recent_locks = [dict(row) for row in recent_cursor.fetchall()]
        
        # Get stats
        stats_cursor = conn.execute('''
            SELECT 
                status,
                COUNT(*) as count,
                SUM(CAST(amount AS REAL)) as total_amount
            FROM bridge_locks
            GROUP BY status
        ''')
        stats = [dict(row) for row in stats_cursor.fetchall()]
    
    dashboard_html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Bridge Dashboard</title>
        <style>
            body { font-family: monospace; margin: 20px; background: #0a0a0a; color: #00ff00; }
            table { border-collapse: collapse; width: 100%; margin: 20px 0; }
            th, td { border: 1px solid #333; padding: 8px; text-align: left; }
            th { background: #1a1a1a; }
            .status-pending { color: #ffff00; }
            .status-released { color: #00ff00; }
            .status-expired { color: #ff4444; }
            .stats { display: flex; gap: 20px; margin: 20px 0; }
            .stat-box { border: 1px solid #333; padding: 15px; min-width: 150px; }
        </style>
    </head>
    <body>
        <h1>🌉 Bridge Dashboard</h1>
        
        <div class="stats">
            {% for stat in stats %}
            <div class="stat-box">
                <strong>{{ stat.status|title }}</strong><br>
                Count: {{ stat.count }}<br>
                Total: {{ stat.total_amount or 0 }} wRTC
            </div>
            {% endfor %}
        </div>
        
        <h2>Recent Locks</h2>
        <table>
            <tr>
                <th>Lock ID</th>
                <th>From → To</th>
                <th>Amount</th>
                <th>Status</th>
                <th>Created</th>
                <th>Expires</th>
            </tr>
            {% for lock in recent_locks %}
            <tr>
                <td><code>{{ lock.lock_id }}</code></td>
                <td>{{ lock.from_chain }} → {{ lock.to_chain }}</td>
                <td>{{ lock.amount }} {{ lock.token_type }}</td>
                <td class="status-{{ lock.status }}">{{ lock.status }}</td>
                <td>{{ lock.created_at|int|datetime }}</td>
                <td>{{ lock.expires_at|int|datetime }}</td>
            </tr>
            {% endfor %}
        </table>
        
        <div style="margin-top: 40px;">
            <h3>API Endpoints</h3>
            <ul>
                <li><code>POST /bridge/lock</code> - Create new lock</li>
                <li><code>POST /bridge/release</code> - Release lock</li>
                <li><code>GET /bridge/status/&lt;lock_id&gt;</code> - Get lock status</li>
                <li><code>GET /bridge/pending</code> - Get pending locks</li>
                <li><code>POST /bridge/cleanup</code> - Cleanup expired locks</li>
            </ul>
        </div>
    </body>
    </html>
    '''
    
    def datetime_filter(timestamp):
        return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
    
    app.jinja_env.filters['datetime'] = datetime_filter
    
    return render_template_string(dashboard_html, 
                                recent_locks=recent_locks, 
                                stats=stats)

if __name__ == '__main__':
    app.run(debug=True, port=5001)