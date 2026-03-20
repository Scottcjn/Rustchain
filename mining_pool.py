// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import sqlite3
import hashlib
import time
import json
import logging
from flask import Flask, request, jsonify, render_template_string
from datetime import datetime, timedelta
import threading
from contextlib import contextmanager

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = 'mining_pool.db'
POOL_FEE = 0.02  # 2% pool fee
MIN_PAYOUT = 1.0  # Minimum payout threshold
DIFFICULTY_TARGET = 0x00000fffff000000000000000000000000000000000000000000000000000000

@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS miners (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wallet_address TEXT UNIQUE NOT NULL,
                nickname TEXT,
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_shares INTEGER DEFAULT 0,
                total_rewards REAL DEFAULT 0.0,
                pending_balance REAL DEFAULT 0.0,
                status TEXT DEFAULT 'active'
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS shares (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                miner_id INTEGER,
                block_hash TEXT,
                nonce TEXT,
                difficulty REAL,
                submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_valid BOOLEAN DEFAULT 0,
                is_block BOOLEAN DEFAULT 0,
                reward_amount REAL DEFAULT 0.0,
                FOREIGN KEY (miner_id) REFERENCES miners (id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS payouts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                miner_id INTEGER,
                amount REAL,
                txn_hash TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processed_at TIMESTAMP,
                FOREIGN KEY (miner_id) REFERENCES miners (id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pool_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                total_hashrate REAL DEFAULT 0.0,
                active_miners INTEGER DEFAULT 0,
                blocks_found INTEGER DEFAULT 0,
                total_rewards REAL DEFAULT 0.0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        conn.commit()

def validate_share(block_hash, nonce, difficulty):
    """Validate submitted mining share"""
    try:
        hash_input = f"{block_hash}{nonce}".encode()
        result_hash = hashlib.sha256(hash_input).hexdigest()

        # Convert to integer for comparison
        hash_int = int(result_hash, 16)
        target = int(difficulty)

        return hash_int < target
    except Exception as e:
        logger.error(f"Share validation error: {e}")
        return False

def calculate_reward_distribution():
    """Calculate and distribute rewards based on shares"""
    with get_db() as conn:
        cursor = conn.cursor()

        # Get recent shares (last 24 hours)
        cursor.execute('''
            SELECT m.id, m.wallet_address, COUNT(s.id) as share_count
            FROM miners m
            JOIN shares s ON m.id = s.miner_id
            WHERE s.submitted_at > datetime('now', '-24 hours')
            AND s.is_valid = 1
            GROUP BY m.id, m.wallet_address
        ''')

        share_data = cursor.fetchall()
        if not share_data:
            return

        total_shares = sum(row[2] for row in share_data)

        # Get pending block rewards
        cursor.execute('''
            SELECT SUM(reward_amount) FROM shares
            WHERE is_block = 1 AND reward_amount > 0
            AND submitted_at > datetime('now', '-24 hours')
        ''')

        result = cursor.fetchone()
        total_reward = result[0] if result[0] else 0.0

        if total_reward > 0:
            pool_fee_amount = total_reward * POOL_FEE
            miner_reward = total_reward - pool_fee_amount

            # Distribute rewards proportionally
            for miner_id, wallet, share_count in share_data:
                miner_portion = (share_count / total_shares) * miner_reward

                cursor.execute('''
                    UPDATE miners
                    SET pending_balance = pending_balance + ?,
                        total_rewards = total_rewards + ?
                    WHERE id = ?
                ''', (miner_portion, miner_portion, miner_id))

            conn.commit()
            logger.info(f"Distributed {miner_reward} RTC among {len(share_data)} miners")

@app.route('/')
def dashboard():
    template = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>RustChain Mining Pool</title>
        <style>
            body { font-family: monospace; margin: 20px; background: #0a0a0a; color: #00ff00; }
            .container { max-width: 1200px; margin: 0 auto; }
            .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; }
            .stat-box { border: 1px solid #00ff00; padding: 15px; background: #111; }
            table { width: 100%; border-collapse: collapse; margin-top: 20px; }
            th, td { border: 1px solid #00ff00; padding: 8px; text-align: left; }
            th { background: #222; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>⛏️ RustChain Mining Pool</h1>

            <div class="stats">
                <div class="stat-box">
                    <h3>Pool Stats</h3>
                    <p>Active Miners: {{ stats.active_miners }}</p>
                    <p>Total Hashrate: {{ "%.2f"|format(stats.total_hashrate) }} H/s</p>
                    <p>Blocks Found: {{ stats.blocks_found }}</p>
                    <p>Total Rewards: {{ "%.4f"|format(stats.total_rewards) }} RTC</p>
                </div>
            </div>

            <h2>Top Miners (24h)</h2>
            <table>
                <thead>
                    <tr>
                        <th>Wallet</th>
                        <th>Nickname</th>
                        <th>Shares</th>
                        <th>Pending Balance</th>
                        <th>Last Active</th>
                    </tr>
                </thead>
                <tbody>
                    {% for miner in miners %}
                    <tr>
                        <td>{{ miner[1][:12] }}...</td>
                        <td>{{ miner[2] or 'Anonymous' }}</td>
                        <td>{{ miner[6] }}</td>
                        <td>{{ "%.4f"|format(miner[7]) }} RTC</td>
                        <td>{{ miner[4] }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>

            <h2>API Endpoints</h2>
            <ul>
                <li>POST /register - Register new miner</li>
                <li>POST /submit - Submit mining share</li>
                <li>GET /stats/&lt;wallet&gt; - Get miner stats</li>
                <li>POST /payout - Request payout</li>
            </ul>
        </div>
    </body>
    </html>
    '''

    with get_db() as conn:
        cursor = conn.cursor()

        # Get pool stats
        cursor.execute('''
            SELECT active_miners, total_hashrate, blocks_found, total_rewards
            FROM pool_stats ORDER BY updated_at DESC LIMIT 1
        ''')
        stats_row = cursor.fetchone()
        stats = {
            'active_miners': stats_row[0] if stats_row else 0,
            'total_hashrate': stats_row[1] if stats_row else 0.0,
            'blocks_found': stats_row[2] if stats_row else 0,
            'total_rewards': stats_row[3] if stats_row else 0.0
        }

        # Get top miners
        cursor.execute('''
            SELECT m.*, COUNT(s.id) as recent_shares, m.pending_balance
            FROM miners m
            LEFT JOIN shares s ON m.id = s.miner_id
                AND s.submitted_at > datetime('now', '-24 hours')
            GROUP BY m.id
            ORDER BY recent_shares DESC, m.total_shares DESC
            LIMIT 10
        ''')
        miners = cursor.fetchall()

    return render_template_string(template, stats=stats, miners=miners)

@app.route('/register', methods=['POST'])
def register_miner():
    """Register new miner in pool"""
    data = request.get_json()
    if not data or 'wallet_address' not in data:
        return jsonify({'error': 'wallet_address required'}), 400

    wallet_address = data['wallet_address']
    nickname = data.get('nickname', '')

    with get_db() as conn:
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO miners (wallet_address, nickname)
                VALUES (?, ?)
            ''', (wallet_address, nickname))

            miner_id = cursor.lastrowid
            conn.commit()

            logger.info(f"New miner registered: {wallet_address[:12]}...")
            return jsonify({
                'success': True,
                'miner_id': miner_id,
                'message': 'Miner registered successfully'
            })

        except sqlite3.IntegrityError:
            return jsonify({'error': 'Wallet already registered'}), 409

@app.route('/submit', methods=['POST'])
def submit_share():
    """Submit mining share for validation"""
    data = request.get_json()
    required_fields = ['wallet_address', 'block_hash', 'nonce', 'difficulty']

    if not data or not all(field in data for field in required_fields):
        return jsonify({'error': 'Missing required fields'}), 400

    wallet_address = data['wallet_address']
    block_hash = data['block_hash']
    nonce = data['nonce']
    difficulty = float(data['difficulty'])

    with get_db() as conn:
        cursor = conn.cursor()

        # Get miner ID
        cursor.execute('SELECT id FROM miners WHERE wallet_address = ?', (wallet_address,))
        miner_row = cursor.fetchone()

        if not miner_row:
            return jsonify({'error': 'Miner not registered'}), 404

        miner_id = miner_row[0]

        # Validate share
        is_valid = validate_share(block_hash, nonce, difficulty)
        is_block = difficulty >= DIFFICULTY_TARGET if is_valid else False
        reward_amount = 50.0 if is_block else 0.0  # Block reward

        # Store share
        cursor.execute('''
            INSERT INTO shares (miner_id, block_hash, nonce, difficulty, is_valid, is_block, reward_amount)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (miner_id, block_hash, nonce, difficulty, is_valid, is_block, reward_amount))

        if is_valid:
            # Update miner stats
            cursor.execute('''
                UPDATE miners
                SET total_shares = total_shares + 1, last_active = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (miner_id,))

        conn.commit()

        response = {
            'valid': is_valid,
            'block_found': is_block,
            'reward': reward_amount
        }

        if is_block:
            logger.info(f"BLOCK FOUND by {wallet_address[:12]}... - Reward: {reward_amount} RTC")

        return jsonify(response)

@app.route('/stats/<wallet_address>')
def get_miner_stats(wallet_address):
    """Get miner statistics"""
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute('''
            SELECT m.*, COUNT(s.id) as total_shares_db,
                   COUNT(CASE WHEN s.is_valid = 1 THEN 1 END) as valid_shares,
                   COUNT(CASE WHEN s.is_block = 1 THEN 1 END) as blocks_found
            FROM miners m
            LEFT JOIN shares s ON m.id = s.miner_id
            WHERE m.wallet_address = ?
            GROUP BY m.id
        ''', (wallet_address,))

        result = cursor.fetchone()
        if not result:
            return jsonify({'error': 'Miner not found'}), 404

        # Get recent shares (24h)
        cursor.execute('''
            SELECT COUNT(*) FROM shares s
            JOIN miners m ON s.miner_id = m.id
            WHERE m.wallet_address = ?
            AND s.submitted_at > datetime('now', '-24 hours')
            AND s.is_valid = 1
        ''', (wallet_address,))

        recent_shares = cursor.fetchone()[0]

        stats = {
            'wallet_address': result[1],
            'nickname': result[2],
            'registered_at': result[3],
            'total_shares': result[5],
            'valid_shares': result[7],
            'blocks_found': result[8],
            'total_rewards': result[6],
            'pending_balance': result[7],
            'recent_shares_24h': recent_shares,
            'status': result[8]
        }

        return jsonify(stats)

@app.route('/payout', methods=['POST'])
def request_payout():
    """Process payout request"""
    data = request.get_json()
    if not data or 'wallet_address' not in data:
        return jsonify({'error': 'wallet_address required'}), 400

    wallet_address = data['wallet_address']

    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, pending_balance FROM miners WHERE wallet_address = ?
        ''', (wallet_address,))

        result = cursor.fetchone()
        if not result:
            return jsonify({'error': 'Miner not found'}), 404

        miner_id, pending_balance = result

        if pending_balance < MIN_PAYOUT:
            return jsonify({
                'error': f'Minimum payout is {MIN_PAYOUT} RTC',
                'pending_balance': pending_balance
            }), 400

        # Create payout record
        payout_hash = hashlib.sha256(f"{wallet_address}{time.time()}".encode()).hexdigest()

        cursor.execute('''
            INSERT INTO payouts (miner_id, amount, txn_hash, status)
            VALUES (?, ?, ?, 'processing')
        ''', (miner_id, pending_balance, payout_hash))

        # Reset pending balance
        cursor.execute('''
            UPDATE miners SET pending_balance = 0.0 WHERE id = ?
        ''', (miner_id,))

        conn.commit()

        logger.info(f"Payout requested: {pending_balance} RTC to {wallet_address[:12]}...")

        return jsonify({
            'success': True,
            'amount': pending_balance,
            'txn_hash': payout_hash,
            'status': 'processing'
        })

def update_pool_stats():
    """Background task to update pool statistics"""
    while True:
        try:
            with get_db() as conn:
                cursor = conn.cursor()

                # Count active miners (active in last hour)
                cursor.execute('''
                    SELECT COUNT(*) FROM miners
                    WHERE last_active > datetime('now', '-1 hour')
                ''')
                active_miners = cursor.fetchone()[0]

                # Calculate total blocks found
                cursor.execute('SELECT COUNT(*) FROM shares WHERE is_block = 1')
                blocks_found = cursor.fetchone()[0]

                # Calculate total rewards distributed
                cursor.execute('SELECT SUM(total_rewards) FROM miners')
                result = cursor.fetchone()
                total_rewards = result[0] if result[0] else 0.0

                # Estimate hashrate based on recent shares
                cursor.execute('''
                    SELECT COUNT(*) FROM shares
                    WHERE submitted_at > datetime('now', '-10 minutes')
                    AND is_valid = 1
                ''')
                recent_shares = cursor.fetchone()[0]
                estimated_hashrate = recent_shares * 6  # Rough estimate

                # Update or insert stats
                cursor.execute('''
                    INSERT OR REPLACE INTO pool_stats
                    (id, active_miners, total_hashrate, blocks_found, total_rewards, updated_at)
                    VALUES (1, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ''', (active_miners, estimated_hashrate, blocks_found, total_rewards))

                conn.commit()

        except Exception as e:
            logger.error(f"Stats update error: {e}")

        time.sleep(60)  # Update every minute

if __name__ == '__main__':
    init_db()

    # Start background stats updater
    stats_thread = threading.Thread(target=update_pool_stats, daemon=True)
    stats_thread.start()

    # Start reward distribution scheduler
    def reward_scheduler():
        while True:
            try:
                calculate_reward_distribution()
                time.sleep(3600)  # Run every hour
            except Exception as e:
                logger.error(f"Reward distribution error: {e}")
                time.sleep(300)  # Retry in 5 minutes

    reward_thread = threading.Thread(target=reward_scheduler, daemon=True)
    reward_thread.start()

    logger.info("Mining pool server starting...")
    app.run(host='0.0.0.0', port=8080, debug=False)
