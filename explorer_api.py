# SPDX-License-Identifier: MIT

from flask import Flask, request, jsonify
import sqlite3
import json
from datetime import datetime, timedelta
import os
import logging

DB_PATH = 'rustchain.db'

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_db():
    """Initialize database tables if they don't exist"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS miners (
                wallet_address TEXT PRIMARY KEY,
                architecture TEXT,
                antiquity_multiplier REAL DEFAULT 1.0,
                last_attestation TIMESTAMP,
                status TEXT DEFAULT 'offline',
                total_blocks INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS agent_jobs (
                job_id TEXT PRIMARY KEY,
                agent_address TEXT,
                job_type TEXT,
                status TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                reward REAL DEFAULT 0.0
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS epochs (
                epoch_number INTEGER PRIMARY KEY,
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                total_transactions INTEGER DEFAULT 0,
                network_difficulty REAL DEFAULT 1.0
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS wallets (
                address TEXT PRIMARY KEY,
                balance REAL DEFAULT 0.0,
                transaction_count INTEGER DEFAULT 0,
                last_activity TIMESTAMP
            )
        ''')

        conn.commit()

@app.route('/api/miners', methods=['GET'])
def get_miners():
    """Get all miners with their status and stats"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT wallet_address, architecture, antiquity_multiplier,
                       last_attestation, status, total_blocks
                FROM miners
                ORDER BY last_attestation DESC
            ''')

            miners = []
            current_time = datetime.now()

            for row in cursor.fetchall():
                miner_data = dict(row)

                # Determine online/offline status based on last attestation
                if miner_data['last_attestation']:
                    last_seen = datetime.fromisoformat(miner_data['last_attestation'])
                    time_diff = current_time - last_seen
                    miner_data['is_online'] = time_diff.total_seconds() < 300  # 5 minutes
                else:
                    miner_data['is_online'] = False

                miners.append(miner_data)

            return jsonify({
                'success': True,
                'miners': miners,
                'total_count': len(miners),
                'online_count': sum(1 for m in miners if m['is_online'])
            })

    except Exception as e:
        logger.error(f"Error fetching miners: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/agent/jobs', methods=['GET'])
def get_agent_jobs():
    """Get agent jobs with optional filtering"""
    try:
        status_filter = request.args.get('status')
        limit = int(request.args.get('limit', 50))

        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            query = '''
                SELECT job_id, agent_address, job_type, status,
                       created_at, completed_at, reward
                FROM agent_jobs
            '''
            params = []

            if status_filter:
                query += ' WHERE status = ?'
                params.append(status_filter)

            query += ' ORDER BY created_at DESC LIMIT ?'
            params.append(limit)

            cursor.execute(query, params)
            jobs = [dict(row) for row in cursor.fetchall()]

            return jsonify({
                'success': True,
                'jobs': jobs,
                'total_count': len(jobs)
            })

    except Exception as e:
        logger.error(f"Error fetching agent jobs: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/agent/stats', methods=['GET'])
def get_agent_stats():
    """Get agent statistics"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # Get job counts by status
            cursor.execute('''
                SELECT status, COUNT(*) as count
                FROM agent_jobs
                GROUP BY status
            ''')

            status_counts = dict(cursor.fetchall())

            # Get total rewards
            cursor.execute('SELECT SUM(reward) FROM agent_jobs WHERE reward > 0')
            total_rewards = cursor.fetchone()[0] or 0

            # Get active agents count
            cursor.execute('''
                SELECT COUNT(DISTINCT agent_address)
                FROM agent_jobs
                WHERE created_at > datetime('now', '-24 hours')
            ''')
            active_agents = cursor.fetchone()[0] or 0

            return jsonify({
                'success': True,
                'stats': {
                    'status_counts': status_counts,
                    'total_rewards': total_rewards,
                    'active_agents_24h': active_agents
                }
            })

    except Exception as e:
        logger.error(f"Error fetching agent stats: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/wallet/<address>', methods=['GET'])
def get_wallet_info(address):
    """Get wallet information by address"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Get wallet data
            cursor.execute('''
                SELECT address, balance, transaction_count, last_activity
                FROM wallets
                WHERE address = ?
            ''', (address,))

            wallet = cursor.fetchone()

            if not wallet:
                return jsonify({
                    'success': False,
                    'error': 'Wallet not found'
                }), 404

            wallet_data = dict(wallet)

            # Check if this address is also a miner
            cursor.execute('''
                SELECT architecture, antiquity_multiplier, status, total_blocks
                FROM miners
                WHERE wallet_address = ?
            ''', (address,))

            miner_info = cursor.fetchone()
            if miner_info:
                wallet_data['miner_info'] = dict(miner_info)

            return jsonify({
                'success': True,
                'wallet': wallet_data
            })

    except Exception as e:
        logger.error(f"Error fetching wallet {address}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/epochs', methods=['GET'])
def get_epochs():
    """Get epoch history"""
    try:
        limit = int(request.args.get('limit', 20))

        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT epoch_number, start_time, end_time,
                       total_transactions, network_difficulty
                FROM epochs
                ORDER BY epoch_number DESC
                LIMIT ?
            ''', (limit,))

            epochs = [dict(row) for row in cursor.fetchall()]

            return jsonify({
                'success': True,
                'epochs': epochs,
                'count': len(epochs)
            })

    except Exception as e:
        logger.error(f"Error fetching epochs: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/network/health', methods=['GET'])
def get_network_health():
    """Get network health metrics"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # Count online miners
            current_time = datetime.now()
            cutoff_time = current_time - timedelta(minutes=5)

            cursor.execute('''
                SELECT COUNT(*) FROM miners
                WHERE last_attestation > ? OR status = 'online'
            ''', (cutoff_time.isoformat(),))

            online_miners = cursor.fetchone()[0] or 0

            cursor.execute('SELECT COUNT(*) FROM miners')
            total_miners = cursor.fetchone()[0] or 0

            # Get recent job activity
            recent_cutoff = current_time - timedelta(hours=1)
            cursor.execute('''
                SELECT COUNT(*) FROM agent_jobs
                WHERE created_at > ?
            ''', (recent_cutoff.isoformat(),))

            recent_jobs = cursor.fetchone()[0] or 0

            # Calculate network health score
            miner_ratio = online_miners / max(total_miners, 1)
            job_activity_score = min(recent_jobs / 10.0, 1.0)  # Scale jobs to 0-1
            health_score = (miner_ratio * 0.7 + job_activity_score * 0.3) * 100

            return jsonify({
                'success': True,
                'health': {
                    'online_miners': online_miners,
                    'total_miners': total_miners,
                    'recent_jobs': recent_jobs,
                    'health_score': round(health_score, 1),
                    'status': 'healthy' if health_score > 70 else 'warning' if health_score > 40 else 'critical'
                }
            })

    except Exception as e:
        logger.error(f"Error fetching network health: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Basic health check endpoint"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT 1')

        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'database': 'connected'
        })

    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
