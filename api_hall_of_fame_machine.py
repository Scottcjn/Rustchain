# SPDX-License-Identifier: MIT

from flask import Flask, jsonify, request
import sqlite3
import json
from datetime import datetime

app = Flask(__name__)

DB_PATH = 'blockchain.db'

def get_machine_details(fingerprint_hash):
    """Get full machine details from hall_of_rust table"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get basic machine info
        cursor.execute("""
            SELECT * FROM hall_of_rust
            WHERE fingerprint_hash = ?
            ORDER BY epoch DESC
            LIMIT 1
        """, (fingerprint_hash,))

        machine = cursor.fetchone()
        if not machine:
            return None

        # Get attestation timeline
        cursor.execute("""
            SELECT epoch, rust_score, timestamp, rewards_earned
            FROM hall_of_rust
            WHERE fingerprint_hash = ?
            ORDER BY epoch ASC
        """, (fingerprint_hash,))

        timeline = cursor.fetchall()

        # Get participation stats
        cursor.execute("""
            SELECT
                COUNT(*) as total_epochs,
                MIN(epoch) as first_epoch,
                MAX(epoch) as latest_epoch,
                AVG(rust_score) as avg_rust_score,
                SUM(rewards_earned) as total_rewards
            FROM hall_of_rust
            WHERE fingerprint_hash = ?
        """, (fingerprint_hash,))

        stats = cursor.fetchone()

        # Get fleet averages for comparison
        cursor.execute("""
            SELECT
                AVG(rust_score) as fleet_avg_score,
                COUNT(DISTINCT fingerprint_hash) as total_machines
            FROM hall_of_rust
            WHERE epoch = (SELECT MAX(epoch) FROM hall_of_rust)
        """)

        fleet_stats = cursor.fetchone()

        return {
            'machine': dict(machine),
            'timeline': [dict(row) for row in timeline],
            'stats': dict(stats),
            'fleet_comparison': dict(fleet_stats)
        }

def get_machine_rank(fingerprint_hash, current_epoch=None):
    """Get current ranking of machine"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        if not current_epoch:
            cursor.execute("SELECT MAX(epoch) FROM hall_of_rust")
            current_epoch = cursor.fetchone()[0]

        cursor.execute("""
            SELECT
                COUNT(*) + 1 as rank
            FROM hall_of_rust h1
            WHERE h1.epoch = ? AND h1.rust_score > (
                SELECT h2.rust_score
                FROM hall_of_rust h2
                WHERE h2.fingerprint_hash = ? AND h2.epoch = ?
            )
        """, (current_epoch, fingerprint_hash, current_epoch))

        result = cursor.fetchone()
        return result[0] if result else None

@app.route('/api/hall_of_fame/machine')
def api_hall_of_fame_machine():
    """API endpoint for machine details"""
    try:
        machine_id = request.args.get('id')
        if not machine_id:
            return jsonify({
                'success': False,
                'error': 'Machine ID parameter required'
            }), 400

        machine_data = get_machine_details(machine_id)
        if not machine_data:
            return jsonify({
                'success': False,
                'error': 'Machine not found'
            }), 404

        # Add current rank
        current_rank = get_machine_rank(machine_id)

        response_data = {
            'success': True,
            'data': {
                'fingerprint_hash': machine_id,
                'current_rank': current_rank,
                'machine_info': machine_data['machine'],
                'participation_stats': machine_data['stats'],
                'attestation_timeline': machine_data['timeline'],
                'fleet_comparison': machine_data['fleet_comparison']
            },
            'metadata': {
                'retrieved_at': datetime.utcnow().isoformat(),
                'total_epochs': len(machine_data['timeline'])
            }
        }

        return jsonify(response_data)

    except sqlite3.Error as e:
        return jsonify({
            'success': False,
            'error': f'Database error: {str(e)}'
        }), 500

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Internal server error: {str(e)}'
        }), 500

@app.route('/api/hall_of_fame/machine/timeline')
def api_machine_timeline():
    """Get detailed timeline data for charting"""
    try:
        machine_id = request.args.get('id')
        limit = request.args.get('limit', 100, type=int)

        if not machine_id:
            return jsonify({
                'success': False,
                'error': 'Machine ID required'
            }), 400

        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    epoch,
                    rust_score,
                    timestamp,
                    rewards_earned,
                    strftime('%Y-%m-%d', timestamp) as date_formatted
                FROM hall_of_rust
                WHERE fingerprint_hash = ?
                ORDER BY epoch DESC
                LIMIT ?
            """, (machine_id, limit))

            timeline_data = [dict(row) for row in cursor.fetchall()]

            return jsonify({
                'success': True,
                'data': {
                    'machine_id': machine_id,
                    'timeline': timeline_data,
                    'count': len(timeline_data)
                }
            })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    app.run(debug=True)
