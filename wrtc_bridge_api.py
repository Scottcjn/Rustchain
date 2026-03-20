// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

from flask import Flask, request, jsonify, render_template_string
import sqlite3
import hashlib
import time
import json
import os
from datetime import datetime, timedelta

DB_PATH = 'wrtc_bridge.db'

app = Flask(__name__)

def init_bridge_db():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bridge_locks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lock_id TEXT UNIQUE NOT NULL,
                source_chain TEXT NOT NULL,
                target_chain TEXT NOT NULL,
                user_address TEXT NOT NULL,
                amount INTEGER NOT NULL,
                lock_hash TEXT NOT NULL,
                status TEXT DEFAULT 'locked',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                released_at TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS anti_sybil_registry (
                address TEXT PRIMARY KEY,
                chain TEXT NOT NULL,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                lock_count INTEGER DEFAULT 0,
                total_locked INTEGER DEFAULT 0,
                last_lock_time TIMESTAMP,
                reputation_score INTEGER DEFAULT 100
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bridge_validators (
                validator_id TEXT PRIMARY KEY,
                public_key TEXT NOT NULL,
                active INTEGER DEFAULT 1,
                total_validations INTEGER DEFAULT 0
            )
        ''')

        conn.commit()

def generate_lock_id(user_addr, amount, timestamp):
    data = f"{user_addr}{amount}{timestamp}"
    return hashlib.sha256(data.encode()).hexdigest()[:16]

def validate_chain_params(chain_name):
    supported_chains = {
        'rustchain': {'min_lock': 1000, 'max_lock': 100000},
        'solana': {'min_lock': 100, 'max_lock': 50000},
        'base': {'min_lock': 100, 'max_lock': 50000}
    }
    return supported_chains.get(chain_name.lower())

def check_anti_sybil(address, chain, amount):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        cursor.execute('''
            SELECT lock_count, total_locked, last_lock_time, reputation_score
            FROM anti_sybil_registry
            WHERE address = ? AND chain = ?
        ''', (address, chain))

        result = cursor.fetchone()

        if not result:
            cursor.execute('''
                INSERT INTO anti_sybil_registry (address, chain, lock_count, total_locked)
                VALUES (?, ?, 0, 0)
            ''', (address, chain))
            return True, "New address registered"

        lock_count, total_locked, last_lock, reputation = result

        # Rate limiting - max 5 locks per hour
        if last_lock:
            last_lock_dt = datetime.fromisoformat(last_lock.replace('Z', '+00:00'))
            if datetime.utcnow() - last_lock_dt < timedelta(minutes=12) and lock_count >= 5:
                return False, "Rate limit exceeded"

        # Volume limits based on reputation
        daily_limit = 10000 if reputation > 80 else 5000
        if total_locked + amount > daily_limit:
            return False, f"Daily volume limit exceeded: {daily_limit}"

        return True, "Validation passed"

@app.route('/bridge/lock', methods=['POST'])
def bridge_lock():
    try:
        data = request.get_json()

        required_fields = ['user_address', 'source_chain', 'target_chain', 'amount', 'lock_hash']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400

        user_address = data['user_address']
        source_chain = data['source_chain']
        target_chain = data['target_chain']
        amount = int(data['amount'])
        lock_hash = data['lock_hash']

        # Validate chain parameters
        source_params = validate_chain_params(source_chain)
        target_params = validate_chain_params(target_chain)

        if not source_params or not target_params:
            return jsonify({'error': 'Unsupported chain'}), 400

        if amount < source_params['min_lock'] or amount > source_params['max_lock']:
            return jsonify({
                'error': f'Amount outside valid range: {source_params["min_lock"]}-{source_params["max_lock"]}'
            }), 400

        # Anti-Sybil validation
        is_valid, message = check_anti_sybil(user_address, source_chain, amount)
        if not is_valid:
            return jsonify({'error': f'Anti-Sybil check failed: {message}'}), 403

        # Generate lock ID and expiry
        timestamp = int(time.time())
        lock_id = generate_lock_id(user_address, amount, timestamp)
        expires_at = datetime.utcnow() + timedelta(hours=24)

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            try:
                cursor.execute('''
                    INSERT INTO bridge_locks
                    (lock_id, source_chain, target_chain, user_address, amount, lock_hash, expires_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (lock_id, source_chain, target_chain, user_address, amount, lock_hash, expires_at))

                # Update anti-sybil registry
                cursor.execute('''
                    UPDATE anti_sybil_registry
                    SET lock_count = lock_count + 1,
                        total_locked = total_locked + ?,
                        last_lock_time = CURRENT_TIMESTAMP
                    WHERE address = ? AND chain = ?
                ''', (amount, user_address, source_chain))

                conn.commit()

                return jsonify({
                    'success': True,
                    'lock_id': lock_id,
                    'expires_at': expires_at.isoformat(),
                    'status': 'locked',
                    'message': 'Tokens locked successfully'
                })

            except sqlite3.IntegrityError:
                return jsonify({'error': 'Lock ID collision, please retry'}), 409

    except Exception as e:
        return jsonify({'error': f'Lock operation failed: {str(e)}'}), 500

@app.route('/bridge/release', methods=['POST'])
def bridge_release():
    try:
        data = request.get_json()

        if 'lock_id' not in data:
            return jsonify({'error': 'Missing lock_id'}), 400

        lock_id = data['lock_id']
        validator_sig = data.get('validator_signature', '')

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT lock_id, source_chain, target_chain, user_address, amount, status, expires_at
                FROM bridge_locks
                WHERE lock_id = ?
            ''', (lock_id,))

            lock_record = cursor.fetchone()

            if not lock_record:
                return jsonify({'error': 'Lock not found'}), 404

            _, source_chain, target_chain, user_address, amount, status, expires_at = lock_record

            if status != 'locked':
                return jsonify({'error': f'Lock already {status}'}), 400

            # Check expiry
            if expires_at:
                expiry_dt = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                if datetime.utcnow() > expiry_dt:
                    cursor.execute('UPDATE bridge_locks SET status = ? WHERE lock_id = ?', ('expired', lock_id))
                    conn.commit()
                    return jsonify({'error': 'Lock has expired'}), 410

            # Release the lock
            cursor.execute('''
                UPDATE bridge_locks
                SET status = ?, released_at = CURRENT_TIMESTAMP
                WHERE lock_id = ?
            ''', ('released', lock_id))

            conn.commit()

            return jsonify({
                'success': True,
                'lock_id': lock_id,
                'source_chain': source_chain,
                'target_chain': target_chain,
                'user_address': user_address,
                'amount': amount,
                'status': 'released',
                'message': 'Tokens released for minting on target chain'
            })

    except Exception as e:
        return jsonify({'error': f'Release operation failed: {str(e)}'}), 500

@app.route('/bridge/status/<lock_id>')
def bridge_status(lock_id):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        cursor.execute('''
            SELECT lock_id, source_chain, target_chain, user_address, amount,
                   status, created_at, expires_at, released_at
            FROM bridge_locks
            WHERE lock_id = ?
        ''', (lock_id,))

        result = cursor.fetchone()

        if not result:
            return jsonify({'error': 'Lock not found'}), 404

        lock_data = {
            'lock_id': result[0],
            'source_chain': result[1],
            'target_chain': result[2],
            'user_address': result[3],
            'amount': result[4],
            'status': result[5],
            'created_at': result[6],
            'expires_at': result[7],
            'released_at': result[8]
        }

        return jsonify(lock_data)

@app.route('/bridge/stats')
def bridge_stats():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        cursor.execute('''
            SELECT
                COUNT(*) as total_locks,
                SUM(CASE WHEN status = 'locked' THEN 1 ELSE 0 END) as active_locks,
                SUM(CASE WHEN status = 'released' THEN 1 ELSE 0 END) as released_locks,
                SUM(amount) as total_volume
            FROM bridge_locks
        ''')

        stats = cursor.fetchone()

        cursor.execute('''
            SELECT source_chain, target_chain, COUNT(*), SUM(amount)
            FROM bridge_locks
            GROUP BY source_chain, target_chain
        ''')

        chain_stats = cursor.fetchall()

        return jsonify({
            'total_locks': stats[0] or 0,
            'active_locks': stats[1] or 0,
            'released_locks': stats[2] or 0,
            'total_volume': stats[3] or 0,
            'chain_pairs': [
                {
                    'source': row[0],
                    'target': row[1],
                    'count': row[2],
                    'volume': row[3]
                }
                for row in chain_stats
            ]
        })

@app.route('/bridge/dashboard')
def bridge_dashboard():
    template = '''
<!DOCTYPE html>
<html>
<head>
    <title>wRTC Bridge Dashboard</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #1a1a1a; color: #fff; }
        .container { max-width: 1200px; margin: 0 auto; }
        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .stat-card { background: #2d2d2d; padding: 20px; border-radius: 8px; text-align: center; }
        .stat-number { font-size: 2em; font-weight: bold; color: #ff6b35; }
        .stat-label { color: #ccc; margin-top: 5px; }
        table { width: 100%; border-collapse: collapse; background: #2d2d2d; border-radius: 8px; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #444; }
        th { background: #3d3d3d; }
        .status-locked { color: #ff6b35; }
        .status-released { color: #4caf50; }
        .status-expired { color: #f44336; }
        h1, h2 { color: #ff6b35; }
    </style>
</head>
<body>
    <div class="container">
        <h1>wRTC Cross-Chain Bridge</h1>

        <div class="stats">
            <div class="stat-card">
                <div class="stat-number" id="totalLocks">-</div>
                <div class="stat-label">Total Locks</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="activeLocks">-</div>
                <div class="stat-label">Active Locks</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="totalVolume">-</div>
                <div class="stat-label">Total Volume</div>
            </div>
        </div>

        <h2>Recent Locks</h2>
        <table id="locksTable">
            <thead>
                <tr>
                    <th>Lock ID</th>
                    <th>Source → Target</th>
                    <th>Amount</th>
                    <th>Status</th>
                    <th>Created</th>
                </tr>
            </thead>
            <tbody>
                <tr><td colspan="5">Loading...</td></tr>
            </tbody>
        </table>
    </div>

    <script>
        async function loadStats() {
            try {
                const response = await fetch('/bridge/stats');
                const data = await response.json();

                document.getElementById('totalLocks').textContent = data.total_locks;
                document.getElementById('activeLocks').textContent = data.active_locks;
                document.getElementById('totalVolume').textContent = data.total_volume.toLocaleString();
            } catch (e) {
                console.error('Failed to load stats:', e);
            }
        }

        loadStats();
        setInterval(loadStats, 30000);
    </script>
</body>
</html>
    '''
    return render_template_string(template)

if __name__ == '__main__':
    if not os.path.exists(DB_PATH):
        init_bridge_db()

    app.run(host='0.0.0.0', port=5002, debug=True)
