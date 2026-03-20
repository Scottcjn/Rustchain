# SPDX-License-Identifier: MIT
"""
Flask API bridge for Java SDK integration with RustChain
Provides REST endpoints for wallet operations, block explorer, and mining status
"""

import sqlite3
import json
import hashlib
import hmac
import time
from flask import Flask, request, jsonify, render_template_string
from functools import wraps
from contextlib import contextmanager

# Configuration
DB_PATH = "rustchain.db"
API_VERSION = "v1"

app = Flask(__name__)


@contextmanager
def get_db():
    """Database connection context manager"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def require_api_key(f):
    """Decorator for API key authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if not api_key:
            return jsonify({'error': 'API key required', 'code': 'AUTH_REQUIRED'}), 401

        # Simple key validation (could be enhanced with database lookup)
        if len(api_key) < 16:
            return jsonify({'error': 'Invalid API key format', 'code': 'AUTH_INVALID'}), 401

        return f(*args, **kwargs)
    return decorated_function


def init_database():
    """Initialize database tables if they don't exist"""
    with get_db() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS java_bridge_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER NOT NULL,
                endpoint TEXT NOT NULL,
                method TEXT NOT NULL,
                response_code INTEGER,
                execution_time REAL
            )
        ''')

        conn.execute('''
            CREATE TABLE IF NOT EXISTS api_keys (
                key_hash TEXT PRIMARY KEY,
                app_name TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                last_used INTEGER,
                rate_limit INTEGER DEFAULT 100
            )
        ''')
        conn.commit()


def log_api_call(endpoint, method, response_code, exec_time):
    """Log API call for monitoring"""
    try:
        with get_db() as conn:
            conn.execute('''
                INSERT INTO java_bridge_logs
                (timestamp, endpoint, method, response_code, execution_time)
                VALUES (?, ?, ?, ?, ?)
            ''', (int(time.time()), endpoint, method, response_code, exec_time))
            conn.commit()
    except Exception:
        pass  # Don't fail API calls due to logging errors


@app.route('/')
def index():
    """API documentation page"""
    docs = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>RustChain Java Bridge API</title>
        <style>
            body { font-family: monospace; margin: 40px; background: #1a1a1a; color: #00ff41; }
            .endpoint { margin: 20px 0; padding: 10px; border: 1px solid #333; }
            .method { color: #ff6b35; font-weight: bold; }
            .path { color: #4ecdc4; }
            h1 { color: #00ff41; }
            h2 { color: #ffd700; }
        </style>
    </head>
    <body>
        <h1>RustChain Java Bridge API v1</h1>
        <p>REST API bridge for Java SDK integration</p>

        <h2>Authentication</h2>
        <p>Include header: <code>X-API-Key: your_api_key</code></p>

        <h2>Wallet Endpoints</h2>
        <div class="endpoint">
            <span class="method">POST</span> <span class="path">/api/v1/wallet/balance</span><br>
            Get wallet balance by address
        </div>

        <div class="endpoint">
            <span class="method">POST</span> <span class="path">/api/v1/wallet/validate</span><br>
            Validate RTC address format
        </div>

        <div class="endpoint">
            <span class="method">POST</span> <span class="path">/api/v1/wallet/transactions</span><br>
            Get transaction history for address
        </div>

        <h2>Block Explorer</h2>
        <div class="endpoint">
            <span class="method">GET</span> <span class="path">/api/v1/explorer/latest_blocks</span><br>
            Get recent blocks with pagination
        </div>

        <div class="endpoint">
            <span class="method">GET</span> <span class="path">/api/v1/explorer/block/{height}</span><br>
            Get specific block by height
        </div>

        <div class="endpoint">
            <span class="method">GET</span> <span class="path">/api/v1/explorer/stats</span><br>
            Network statistics
        </div>

        <h2>Mining Status</h2>
        <div class="endpoint">
            <span class="method">GET</span> <span class="path">/api/v1/mining/status</span><br>
            Current mining status and metrics
        </div>

        <div class="endpoint">
            <span class="method">GET</span> <span class="path">/api/v1/mining/rewards/{address}</span><br>
            Mining rewards for specific address
        </div>
    </body>
    </html>
    '''
    return render_template_string(docs)


@app.route(f'/api/{API_VERSION}/wallet/balance', methods=['POST'])
@require_api_key
def wallet_balance():
    """Get wallet balance for given address"""
    start_time = time.time()

    try:
        data = request.get_json()
        address = data.get('address')

        if not address:
            return jsonify({'error': 'Address parameter required', 'code': 'MISSING_ADDRESS'}), 400

        # Query balance from blockchain database
        with get_db() as conn:
            result = conn.execute('''
                SELECT SUM(amount) as balance
                FROM transactions
                WHERE recipient_address = ? AND confirmed = 1
            ''', (address,)).fetchone()

            sent_result = conn.execute('''
                SELECT SUM(amount) as sent
                FROM transactions
                WHERE sender_address = ? AND confirmed = 1
            ''', (address,)).fetchone()

        balance = (result['balance'] or 0) - (sent_result['sent'] or 0)

        response = {
            'address': address,
            'balance': max(0, balance),
            'unit': 'RTC',
            'timestamp': int(time.time())
        }

        exec_time = time.time() - start_time
        log_api_call('/api/v1/wallet/balance', 'POST', 200, exec_time)

        return jsonify(response)

    except Exception as e:
        exec_time = time.time() - start_time
        log_api_call('/api/v1/wallet/balance', 'POST', 500, exec_time)
        return jsonify({'error': 'Internal server error', 'code': 'INTERNAL_ERROR'}), 500


@app.route(f'/api/{API_VERSION}/wallet/validate', methods=['POST'])
@require_api_key
def validate_address():
    """Validate RTC address format"""
    start_time = time.time()

    try:
        data = request.get_json()
        address = data.get('address')

        if not address:
            return jsonify({'error': 'Address parameter required', 'code': 'MISSING_ADDRESS'}), 400

        # Basic RTC address validation (64 hex chars)
        is_valid = (
            len(address) == 64 and
            all(c in '0123456789abcdefABCDEF' for c in address)
        )

        response = {
            'address': address,
            'valid': is_valid,
            'format': 'hex64' if is_valid else 'invalid',
            'timestamp': int(time.time())
        }

        exec_time = time.time() - start_time
        log_api_call('/api/v1/wallet/validate', 'POST', 200, exec_time)

        return jsonify(response)

    except Exception as e:
        exec_time = time.time() - start_time
        log_api_call('/api/v1/wallet/validate', 'POST', 500, exec_time)
        return jsonify({'error': 'Internal server error', 'code': 'INTERNAL_ERROR'}), 500


@app.route(f'/api/{API_VERSION}/wallet/transactions', methods=['POST'])
@require_api_key
def wallet_transactions():
    """Get transaction history for address"""
    start_time = time.time()

    try:
        data = request.get_json()
        address = data.get('address')
        limit = min(data.get('limit', 50), 100)  # Cap at 100
        offset = data.get('offset', 0)

        if not address:
            return jsonify({'error': 'Address parameter required', 'code': 'MISSING_ADDRESS'}), 400

        with get_db() as conn:
            transactions = conn.execute('''
                SELECT tx_hash, sender_address, recipient_address, amount,
                       timestamp, confirmed, block_height
                FROM transactions
                WHERE sender_address = ? OR recipient_address = ?
                ORDER BY timestamp DESC
                LIMIT ? OFFSET ?
            ''', (address, address, limit, offset)).fetchall()

        tx_list = []
        for tx in transactions:
            tx_list.append({
                'hash': tx['tx_hash'],
                'from': tx['sender_address'],
                'to': tx['recipient_address'],
                'amount': tx['amount'],
                'timestamp': tx['timestamp'],
                'confirmed': bool(tx['confirmed']),
                'block_height': tx['block_height'],
                'type': 'received' if tx['recipient_address'] == address else 'sent'
            })

        response = {
            'address': address,
            'transactions': tx_list,
            'total_returned': len(tx_list),
            'limit': limit,
            'offset': offset
        }

        exec_time = time.time() - start_time
        log_api_call('/api/v1/wallet/transactions', 'POST', 200, exec_time)

        return jsonify(response)

    except Exception as e:
        exec_time = time.time() - start_time
        log_api_call('/api/v1/wallet/transactions', 'POST', 500, exec_time)
        return jsonify({'error': 'Internal server error', 'code': 'INTERNAL_ERROR'}), 500


@app.route(f'/api/{API_VERSION}/explorer/latest_blocks')
@require_api_key
def latest_blocks():
    """Get recent blocks"""
    start_time = time.time()

    try:
        limit = min(int(request.args.get('limit', 10)), 50)

        with get_db() as conn:
            blocks = conn.execute('''
                SELECT height, hash, previous_hash, timestamp,
                       miner_address, reward, transaction_count
                FROM blocks
                ORDER BY height DESC
                LIMIT ?
            ''', (limit,)).fetchall()

        block_list = []
        for block in blocks:
            block_list.append({
                'height': block['height'],
                'hash': block['hash'],
                'previous_hash': block['previous_hash'],
                'timestamp': block['timestamp'],
                'miner': block['miner_address'],
                'reward': block['reward'],
                'transaction_count': block['transaction_count']
            })

        response = {
            'blocks': block_list,
            'count': len(block_list)
        }

        exec_time = time.time() - start_time
        log_api_call('/api/v1/explorer/latest_blocks', 'GET', 200, exec_time)

        return jsonify(response)

    except Exception as e:
        exec_time = time.time() - start_time
        log_api_call('/api/v1/explorer/latest_blocks', 'GET', 500, exec_time)
        return jsonify({'error': 'Internal server error', 'code': 'INTERNAL_ERROR'}), 500


@app.route(f'/api/{API_VERSION}/explorer/block/<int:height>')
@require_api_key
def get_block(height):
    """Get specific block by height"""
    start_time = time.time()

    try:
        with get_db() as conn:
            block = conn.execute('''
                SELECT height, hash, previous_hash, timestamp,
                       miner_address, reward, transaction_count, nonce, difficulty
                FROM blocks
                WHERE height = ?
            ''', (height,)).fetchone()

        if not block:
            exec_time = time.time() - start_time
            log_api_call(f'/api/v1/explorer/block/{height}', 'GET', 404, exec_time)
            return jsonify({'error': 'Block not found', 'code': 'BLOCK_NOT_FOUND'}), 404

        response = {
            'height': block['height'],
            'hash': block['hash'],
            'previous_hash': block['previous_hash'],
            'timestamp': block['timestamp'],
            'miner': block['miner_address'],
            'reward': block['reward'],
            'transaction_count': block['transaction_count'],
            'nonce': block['nonce'],
            'difficulty': block['difficulty']
        }

        exec_time = time.time() - start_time
        log_api_call(f'/api/v1/explorer/block/{height}', 'GET', 200, exec_time)

        return jsonify(response)

    except Exception as e:
        exec_time = time.time() - start_time
        log_api_call(f'/api/v1/explorer/block/{height}', 'GET', 500, exec_time)
        return jsonify({'error': 'Internal server error', 'code': 'INTERNAL_ERROR'}), 500


@app.route(f'/api/{API_VERSION}/explorer/stats')
@require_api_key
def network_stats():
    """Get network statistics"""
    start_time = time.time()

    try:
        with get_db() as conn:
            # Latest block info
            latest_block = conn.execute('''
                SELECT height, timestamp, difficulty
                FROM blocks
                ORDER BY height DESC
                LIMIT 1
            ''').fetchone()

            # Total transaction count
            tx_count = conn.execute('SELECT COUNT(*) as count FROM transactions').fetchone()

            # Active miners (last 100 blocks)
            if latest_block:
                miners = conn.execute('''
                    SELECT COUNT(DISTINCT miner_address) as count
                    FROM blocks
                    WHERE height > ?
                ''', (max(0, latest_block['height'] - 100),)).fetchone()
            else:
                miners = {'count': 0}

        response = {
            'latest_block_height': latest_block['height'] if latest_block else 0,
            'latest_block_time': latest_block['timestamp'] if latest_block else 0,
            'current_difficulty': latest_block['difficulty'] if latest_block else 0,
            'total_transactions': tx_count['count'],
            'active_miners_last_100': miners['count'],
            'timestamp': int(time.time())
        }

        exec_time = time.time() - start_time
        log_api_call('/api/v1/explorer/stats', 'GET', 200, exec_time)

        return jsonify(response)

    except Exception as e:
        exec_time = time.time() - start_time
        log_api_call('/api/v1/explorer/stats', 'GET', 500, exec_time)
        return jsonify({'error': 'Internal server error', 'code': 'INTERNAL_ERROR'}), 500


@app.route(f'/api/{API_VERSION}/mining/status')
@require_api_key
def mining_status():
    """Get current mining status"""
    start_time = time.time()

    try:
        with get_db() as conn:
            # Get latest mining info
            latest_block = conn.execute('''
                SELECT height, timestamp, difficulty, miner_address, reward
                FROM blocks
                ORDER BY height DESC
                LIMIT 1
            ''').fetchone()

            # Calculate average block time (last 10 blocks)
            if latest_block and latest_block['height'] >= 10:
                block_times = conn.execute('''
                    SELECT timestamp
                    FROM blocks
                    WHERE height > ?
                    ORDER BY height ASC
                ''', (latest_block['height'] - 10,)).fetchall()

                if len(block_times) > 1:
                    time_diffs = []
                    for i in range(1, len(block_times)):
                        time_diffs.append(block_times[i]['timestamp'] - block_times[i-1]['timestamp'])
                    avg_block_time = sum(time_diffs) / len(time_diffs) if time_diffs else 600
                else:
                    avg_block_time = 600
            else:
                avg_block_time = 600

        response = {
            'network_height': latest_block['height'] if latest_block else 0,
            'current_difficulty': latest_block['difficulty'] if latest_block else 1,
            'last_block_time': latest_block['timestamp'] if latest_block else 0,
            'last_miner': latest_block['miner_address'] if latest_block else None,
            'last_reward': latest_block['reward'] if latest_block else 0,
            'average_block_time': round(avg_block_time, 2),
            'target_block_time': 600,
            'mining_active': bool(latest_block and (int(time.time()) - latest_block['timestamp']) < 1800)
        }

        exec_time = time.time() - start_time
        log_api_call('/api/v1/mining/status', 'GET', 200, exec_time)

        return jsonify(response)

    except Exception as e:
        exec_time = time.time() - start_time
        log_api_call('/api/v1/mining/status', 'GET', 500, exec_time)
        return jsonify({'error': 'Internal server error', 'code': 'INTERNAL_ERROR'}), 500


@app.route(f'/api/{API_VERSION}/mining/rewards/<address>')
@require_api_key
def mining_rewards(address):
    """Get mining rewards for specific address"""
    start_time = time.time()

    try:
        limit = min(int(request.args.get('limit', 20)), 100)

        with get_db() as conn:
            rewards = conn.execute('''
                SELECT height, hash, timestamp, reward
                FROM blocks
                WHERE miner_address = ?
                ORDER BY height DESC
                LIMIT ?
            ''', (address, limit)).fetchall()

            total_rewards = conn.execute('''
                SELECT SUM(reward) as total, COUNT(*) as blocks_mined
                FROM blocks
                WHERE miner_address = ?
            ''', (address,)).fetchone()

        reward_list = []
        for reward in rewards:
            reward_list.append({
                'block_height': reward['height'],
                'block_hash': reward['hash'],
                'timestamp': reward['timestamp'],
                'reward': reward['reward']
            })

        response = {
            'miner_address': address,
            'recent_rewards': reward_list,
            'total_rewards': total_rewards['total'] or 0,
            'blocks_mined': total_rewards['blocks_mined'] or 0,
            'returned_count': len(reward_list)
        }

        exec_time = time.time() - start_time
        log_api_call(f'/api/v1/mining/rewards/{address}', 'GET', 200, exec_time)

        return jsonify(response)

    except Exception as e:
        exec_time = time.time() - start_time
        log_api_call(f'/api/v1/mining/rewards/{address}', 'GET', 500, exec_time)
        return jsonify({'error': 'Internal server error', 'code': 'INTERNAL_ERROR'}), 500


@app.route(f'/api/{API_VERSION}/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': int(time.time()),
        'version': API_VERSION
    })


if __name__ == '__main__':
    init_database()
    app.run(debug=False, host='0.0.0.0', port=5000)
