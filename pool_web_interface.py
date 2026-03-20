// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

from flask import Flask, request, jsonify, render_template_string
import sqlite3
import json
import time
from datetime import datetime
import hashlib
import os

app = Flask(__name__)

DB_PATH = 'pool.db'

def init_pool_db():
    """Initialize the mining pool database"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS miners (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wallet_address TEXT UNIQUE NOT NULL,
                alias TEXT,
                registration_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen TIMESTAMP,
                total_shares INTEGER DEFAULT 0,
                total_earnings REAL DEFAULT 0.0,
                status TEXT DEFAULT 'active'
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS shares (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                miner_id INTEGER,
                block_hash TEXT NOT NULL,
                difficulty INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                valid BOOLEAN DEFAULT 1,
                FOREIGN KEY (miner_id) REFERENCES miners (id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS payouts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                miner_id INTEGER,
                amount REAL NOT NULL,
                transaction_hash TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'pending',
                FOREIGN KEY (miner_id) REFERENCES miners (id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pool_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                total_hashrate REAL DEFAULT 0.0,
                active_miners INTEGER DEFAULT 0,
                blocks_found INTEGER DEFAULT 0,
                last_block_time TIMESTAMP,
                pool_fee REAL DEFAULT 2.0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        conn.commit()

# HTML Templates
MAIN_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RustChain Mining Pool</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { background: #2c3e50; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .stat-card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .stat-value { font-size: 2em; font-weight: bold; color: #3498db; }
        .stat-label { color: #7f8c8d; margin-top: 5px; }
        .section { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }
        .btn { background: #3498db; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; }
        .btn:hover { background: #2980b9; }
        input, select { padding: 8px; margin: 5px; border: 1px solid #ddd; border-radius: 4px; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background: #f8f9fa; }
        .nav { margin-bottom: 20px; }
        .nav a { margin-right: 20px; text-decoration: none; color: #3498db; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🦀 RustChain Mining Pool</h1>
            <p>Decentralized mining for the RustChain network</p>
        </div>

        <div class="nav">
            <a href="/">Dashboard</a>
            <a href="/miners">Miners</a>
            <a href="/payouts">Payouts</a>
            <a href="/register">Register</a>
        </div>

        {{ content }}
    </div>

    <script>
        function refreshStats() {
            fetch('/api/stats')
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        updateStatCards(data.stats);
                    }
                });
        }

        function updateStatCards(stats) {
            const elements = {
                'total_hashrate': stats.total_hashrate || 0,
                'active_miners': stats.active_miners || 0,
                'blocks_found': stats.blocks_found || 0
            };

            for (const [key, value] of Object.entries(elements)) {
                const elem = document.getElementById(key);
                if (elem) elem.textContent = value;
            }
        }

        setInterval(refreshStats, 30000);
    </script>
</body>
</html>
'''

DASHBOARD_CONTENT = '''
<div class="stats-grid">
    <div class="stat-card">
        <div class="stat-value" id="total_hashrate">{{ stats.total_hashrate or 0 }}</div>
        <div class="stat-label">Total Hashrate (GH/s)</div>
    </div>
    <div class="stat-card">
        <div class="stat-value" id="active_miners">{{ stats.active_miners or 0 }}</div>
        <div class="stat-label">Active Miners</div>
    </div>
    <div class="stat-card">
        <div class="stat-value" id="blocks_found">{{ stats.blocks_found or 0 }}</div>
        <div class="stat-label">Blocks Found</div>
    </div>
    <div class="stat-card">
        <div class="stat-value">{{ stats.pool_fee or 2.0 }}%</div>
        <div class="stat-label">Pool Fee</div>
    </div>
</div>

<div class="section">
    <h3>Recent Activity</h3>
    <table>
        <thead>
            <tr>
                <th>Time</th>
                <th>Miner</th>
                <th>Event</th>
                <th>Details</th>
            </tr>
        </thead>
        <tbody>
            {% for activity in recent_activity %}
            <tr>
                <td>{{ activity.timestamp }}</td>
                <td>{{ activity.miner_alias or activity.wallet_address[:12] + '...' }}</td>
                <td>{{ activity.event_type }}</td>
                <td>{{ activity.details }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>
'''

MINERS_CONTENT = '''
<div class="section">
    <h3>Registered Miners</h3>
    <table>
        <thead>
            <tr>
                <th>Alias</th>
                <th>Wallet Address</th>
                <th>Total Shares</th>
                <th>Total Earnings</th>
                <th>Last Seen</th>
                <th>Status</th>
            </tr>
        </thead>
        <tbody>
            {% for miner in miners %}
            <tr>
                <td>{{ miner.alias or 'Anonymous' }}</td>
                <td>{{ miner.wallet_address[:12] + '...' if miner.wallet_address|length > 12 else miner.wallet_address }}</td>
                <td>{{ miner.total_shares }}</td>
                <td>{{ miner.total_earnings }} RTC</td>
                <td>{{ miner.last_seen or 'Never' }}</td>
                <td>{{ miner.status }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>
'''

REGISTER_CONTENT = '''
<div class="section">
    <h3>Register New Miner</h3>
    <form id="registerForm">
        <div>
            <label>Wallet Address:</label><br>
            <input type="text" name="wallet_address" placeholder="Your RTC wallet address" style="width: 300px;" required>
        </div>
        <div>
            <label>Alias (Optional):</label><br>
            <input type="text" name="alias" placeholder="Miner nickname" style="width: 300px;">
        </div>
        <div style="margin-top: 20px;">
            <button type="submit" class="btn">Register Miner</button>
        </div>
    </form>

    <div id="registrationResult" style="margin-top: 20px;"></div>
</div>

<script>
document.getElementById('registerForm').addEventListener('submit', function(e) {
    e.preventDefault();

    const formData = new FormData(this);
    const data = {
        wallet_address: formData.get('wallet_address'),
        alias: formData.get('alias')
    };

    fetch('/api/register', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(data)
    })
    .then(response => response.json())
    .then(data => {
        const result = document.getElementById('registrationResult');
        if (data.success) {
            result.innerHTML = '<div style="color: green;">✓ Miner registered successfully!</div>';
            document.getElementById('registerForm').reset();
        } else {
            result.innerHTML = '<div style="color: red;">✗ ' + (data.error || 'Registration failed') + '</div>';
        }
    });
});
</script>
'''

PAYOUTS_CONTENT = '''
<div class="section">
    <h3>Payout History</h3>
    <table>
        <thead>
            <tr>
                <th>Date</th>
                <th>Miner</th>
                <th>Amount</th>
                <th>Transaction Hash</th>
                <th>Status</th>
            </tr>
        </thead>
        <tbody>
            {% for payout in payouts %}
            <tr>
                <td>{{ payout.timestamp }}</td>
                <td>{{ payout.miner_alias or payout.wallet_address[:12] + '...' }}</td>
                <td>{{ payout.amount }} RTC</td>
                <td>{{ payout.transaction_hash[:16] + '...' if payout.transaction_hash else 'Pending' }}</td>
                <td>{{ payout.status.title() }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>
'''

@app.route('/')
def dashboard():
    stats = get_pool_stats()
    recent_activity = get_recent_activity()
    content = render_template_string(DASHBOARD_CONTENT, stats=stats, recent_activity=recent_activity)
    return render_template_string(MAIN_TEMPLATE, content=content)

@app.route('/miners')
def miners_page():
    miners = get_all_miners()
    content = render_template_string(MINERS_CONTENT, miners=miners)
    return render_template_string(MAIN_TEMPLATE, content=content)

@app.route('/register')
def register_page():
    content = render_template_string(REGISTER_CONTENT)
    return render_template_string(MAIN_TEMPLATE, content=content)

@app.route('/payouts')
def payouts_page():
    payouts = get_payout_history()
    content = render_template_string(PAYOUTS_CONTENT, payouts=payouts)
    return render_template_string(MAIN_TEMPLATE, content=content)

@app.route('/api/register', methods=['POST'])
def register_miner():
    try:
        data = request.get_json()
        wallet_address = data.get('wallet_address')
        alias = data.get('alias', '')

        if not wallet_address:
            return jsonify({'success': False, 'error': 'Wallet address required'})

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO miners (wallet_address, alias, registration_time)
                VALUES (?, ?, ?)
            ''', (wallet_address, alias, datetime.now()))
            conn.commit()

        return jsonify({'success': True, 'message': 'Miner registered successfully'})

    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'error': 'Wallet address already registered'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/submit_share', methods=['POST'])
def submit_share():
    try:
        data = request.get_json()
        wallet_address = data.get('wallet_address')
        block_hash = data.get('block_hash')
        difficulty = data.get('difficulty', 1)

        if not wallet_address or not block_hash:
            return jsonify({'success': False, 'error': 'Missing required fields'})

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # Get miner ID
            cursor.execute('SELECT id FROM miners WHERE wallet_address = ?', (wallet_address,))
            miner = cursor.fetchone()

            if not miner:
                return jsonify({'success': False, 'error': 'Miner not registered'})

            miner_id = miner[0]

            # Insert share
            cursor.execute('''
                INSERT INTO shares (miner_id, block_hash, difficulty, timestamp)
                VALUES (?, ?, ?, ?)
            ''', (miner_id, block_hash, difficulty, datetime.now()))

            # Update miner stats
            cursor.execute('''
                UPDATE miners SET total_shares = total_shares + 1, last_seen = ?
                WHERE id = ?
            ''', (datetime.now(), miner_id))

            conn.commit()

        return jsonify({'success': True, 'message': 'Share submitted successfully'})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/stats')
def get_stats_api():
    stats = get_pool_stats()
    return jsonify({'success': True, 'stats': stats})

@app.route('/api/miner/<wallet_address>')
def get_miner_stats(wallet_address):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT m.*,
                       COUNT(s.id) as recent_shares,
                       SUM(p.amount) as pending_balance
                FROM miners m
                LEFT JOIN shares s ON m.id = s.miner_id AND s.timestamp > datetime('now', '-24 hours')
                LEFT JOIN payouts p ON m.id = p.miner_id AND p.status = 'pending'
                WHERE m.wallet_address = ?
                GROUP BY m.id
            ''', (wallet_address,))

            result = cursor.fetchone()
            if not result:
                return jsonify({'success': False, 'error': 'Miner not found'})

            miner_data = {
                'wallet_address': result[1],
                'alias': result[2],
                'total_shares': result[5],
                'total_earnings': result[6],
                'recent_shares': result[8] or 0,
                'pending_balance': result[9] or 0.0,
                'status': result[7]
            }

            return jsonify({'success': True, 'miner': miner_data})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def get_pool_stats():
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # Get active miners count
            cursor.execute('''
                SELECT COUNT(*) FROM miners
                WHERE last_seen > datetime('now', '-1 hour')
            ''')
            active_miners = cursor.fetchone()[0]

            # Get total blocks found
            cursor.execute('SELECT COUNT(DISTINCT block_hash) FROM shares WHERE valid = 1')
            blocks_found = cursor.fetchone()[0]

            # Calculate approximate hashrate (simplified)
            cursor.execute('''
                SELECT COUNT(*) * 10.0 as hashrate
                FROM shares
                WHERE timestamp > datetime('now', '-1 hour')
            ''')
            hashrate_result = cursor.fetchone()
            total_hashrate = hashrate_result[0] if hashrate_result else 0.0

            return {
                'total_hashrate': round(total_hashrate, 2),
                'active_miners': active_miners,
                'blocks_found': blocks_found,
                'pool_fee': 2.0
            }

    except Exception:
        return {
            'total_hashrate': 0.0,
            'active_miners': 0,
            'blocks_found': 0,
            'pool_fee': 2.0
        }

def get_all_miners():
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT wallet_address, alias, total_shares, total_earnings,
                       last_seen, status
                FROM miners
                ORDER BY total_shares DESC
            ''')

            miners = []
            for row in cursor.fetchall():
                miners.append({
                    'wallet_address': row[0],
                    'alias': row[1],
                    'total_shares': row[2],
                    'total_earnings': row[3],
                    'last_seen': row[4],
                    'status': row[5]
                })

            return miners

    except Exception:
        return []

def get_recent_activity():
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT s.timestamp, m.wallet_address, m.alias, 'Share Submitted' as event_type,
                       'Difficulty: ' || s.difficulty as details
                FROM shares s
                JOIN miners m ON s.miner_id = m.id
                ORDER BY s.timestamp DESC
                LIMIT 10
            ''')

            activity = []
            for row in cursor.fetchall():
                activity.append({
                    'timestamp': row[0],
                    'wallet_address': row[1],
                    'miner_alias': row[2],
                    'event_type': row[3],
                    'details': row[4]
                })

            return activity

    except Exception:
        return []

def get_payout_history():
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT p.timestamp, p.amount, p.transaction_hash, p.status,
                       m.wallet_address, m.alias
                FROM payouts p
                JOIN miners m ON p.miner_id = m.id
                ORDER BY p.timestamp DESC
                LIMIT 50
            ''')

            payouts = []
            for row in cursor.fetchall():
                payouts.append({
                    'timestamp': row[0],
                    'amount': row[1],
                    'transaction_hash': row[2],
                    'status': row[3],
                    'wallet_address': row[4],
                    'miner_alias': row[5]
                })

            return payouts

    except Exception:
        return []

if __name__ == '__main__':
    if not os.path.exists(DB_PATH):
        init_pool_db()

    app.run(debug=True, host='0.0.0.0', port=5000)
