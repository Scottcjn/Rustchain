# SPDX-License-Identifier: MIT

from flask import Flask, request, jsonify, render_template_string
import sqlite3
import json
from datetime import datetime

app = Flask(__name__)

DB_PATH = 'rustchain.db'

def init_hall_of_fame_db():
    """Initialize hall_of_fame table if it doesn't exist"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS hall_of_fame (
                fingerprint_hash TEXT PRIMARY KEY,
                machine_name TEXT,
                first_seen TIMESTAMP,
                total_attestations INTEGER DEFAULT 0,
                rust_score INTEGER DEFAULT 0,
                fleet_rank INTEGER
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS attestations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fingerprint_hash TEXT,
                epoch INTEGER,
                rust_score INTEGER,
                timestamp TIMESTAMP,
                FOREIGN KEY (fingerprint_hash) REFERENCES hall_of_fame(fingerprint_hash)
            )
        ''')
        conn.commit()

def get_machine_details(fingerprint_hash):
    """Get detailed machine information"""
    init_hall_of_fame_db()  # Ensure tables exist

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get machine basic info
        cursor.execute('''
            SELECT fingerprint_hash, machine_name, first_seen,
                   total_attestations, rust_score, fleet_rank
            FROM hall_of_fame
            WHERE fingerprint_hash = ?
        ''', (fingerprint_hash,))
        machine = cursor.fetchone()

        if not machine:
            return None

        # Get attestation history
        cursor.execute('''
            SELECT epoch, rust_score, timestamp
            FROM attestations
            WHERE fingerprint_hash = ?
            ORDER BY epoch DESC
            LIMIT 50
        ''', (fingerprint_hash,))
        attestation_history = cursor.fetchall()

        # Get fleet averages for comparison
        cursor.execute('''
            SELECT AVG(rust_score) as avg_score,
                   COUNT(*) as total_machines
            FROM hall_of_fame
        ''')
        fleet_stats = cursor.fetchone()

        return {
            'machine': dict(machine),
            'attestation_history': [dict(row) for row in attestation_history],
            'fleet_stats': dict(fleet_stats)
        }

@app.route('/hall-of-fame/machine')
def machine_detail_page():
    machine_id = request.args.get('id')
    if not machine_id:
        return "Machine ID required", 400

    machine_data = get_machine_details(machine_id)
    if not machine_data:
        return "Machine not found", 404

    machine = machine_data['machine']
    history = machine_data['attestation_history']
    fleet_stats = machine_data['fleet_stats']

    # Calculate performance metrics
    avg_score = sum(h['rust_score'] for h in history) / len(history) if history else 0

    html_template = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Machine Details - {{ machine.machine_name }}</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; background: #1a1a1a; color: #fff; }
            .machine-card { background: #2a2a2a; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
            .metric { display: inline-block; margin-right: 20px; }
            .history-table { width: 100%; border-collapse: collapse; background: #333; }
            .history-table th, .history-table td { padding: 8px; border: 1px solid #555; }
            .history-table th { background: #444; }
            .back-link { color: #4CAF50; text-decoration: none; }
        </style>
    </head>
    <body>
        <a href="/hall-of-fame" class="back-link">← Back to Hall of Fame</a>

        <div class="machine-card">
            <h1>{{ machine.machine_name or 'Machine-' + machine.fingerprint_hash[:8] }}</h1>
            <p><strong>Fingerprint:</strong> {{ machine.fingerprint_hash }}</p>
            <p><strong>First Seen:</strong> {{ machine.first_seen }}</p>

            <div class="metrics">
                <div class="metric">
                    <strong>Current Rust Score:</strong> {{ machine.rust_score }}
                </div>
                <div class="metric">
                    <strong>Fleet Rank:</strong> #{{ machine.fleet_rank }}
                </div>
                <div class="metric">
                    <strong>Total Attestations:</strong> {{ machine.total_attestations }}
                </div>
            </div>
        </div>

        {% if history %}
        <div class="machine-card">
            <h2>Recent Attestation History</h2>
            <table class="history-table">
                <thead>
                    <tr>
                        <th>Epoch</th>
                        <th>Rust Score</th>
                        <th>Timestamp</th>
                    </tr>
                </thead>
                <tbody>
                    {% for attestation in history %}
                    <tr>
                        <td>{{ attestation.epoch }}</td>
                        <td>{{ attestation.rust_score }}</td>
                        <td>{{ attestation.timestamp }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        {% endif %}

        <div class="machine-card">
            <h2>Fleet Comparison</h2>
            <p><strong>Fleet Average Score:</strong> {{ "%.1f"|format(fleet_stats.avg_score or 0) }}</p>
            <p><strong>Total Fleet Machines:</strong> {{ fleet_stats.total_machines }}</p>
        </div>
    </body>
    </html>
    '''

    return render_template_string(html_template,
                                machine=machine,
                                history=history,
                                fleet_stats=fleet_stats)

if __name__ == '__main__':
    app.run(debug=True)
