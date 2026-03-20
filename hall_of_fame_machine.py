# SPDX-License-Identifier: MIT

from flask import Flask, request, jsonify, render_template_string
import sqlite3
import json
from datetime import datetime

app = Flask(__name__)

DB_PATH = 'rustchain.db'

def get_machine_details(fingerprint_hash):
    """Get detailed machine information"""
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
    avg_score = fleet_stats['avg_score'] or 0
    performance_vs_fleet = (machine['rust_score'] - avg_score) / avg_score * 100 if avg_score > 0 else 0

    html_template = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Machine Profile - {{ machine.machine_name }}</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; background: #0a0a0f; color: #e0e0e0; }
            .header { background: linear-gradient(135deg, #1a1a2e, #16213e); padding: 20px; border-radius: 10px; margin-bottom: 20px; }
            .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 15px; margin: 20px 0; }
            .stat-card { background: #1a1a2e; padding: 15px; border-radius: 8px; border-left: 4px solid #ff6b35; }
            .history { background: #1a1a2e; padding: 20px; border-radius: 10px; margin-top: 20px; }
            .attestation-row { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #333; }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>{{ machine.machine_name }}</h1>
            <p>Fingerprint: <code>{{ machine.fingerprint_hash }}</code></p>
            <p>Fleet Rank: #{{ machine.fleet_rank }}</p>
        </div>

        <div class="stats-grid">
            <div class="stat-card">
                <h3>Rust Score</h3>
                <div style="font-size: 2em; color: #ff6b35;">{{ machine.rust_score }}</div>
                <p>{{ "+%.1f" % performance_vs_fleet if performance_vs_fleet >= 0 else "%.1f" % performance_vs_fleet }}% vs fleet avg</p>
            </div>
            <div class="stat-card">
                <h3>Total Attestations</h3>
                <div style="font-size: 2em;">{{ machine.total_attestations }}</div>
                <p>Since {{ machine.first_seen }}</p>
            </div>
        </div>

        <div class="history">
            <h2>Recent Attestation History</h2>
            {% for att in history %}
            <div class="attestation-row">
                <span>Epoch {{ att.epoch }}</span>
                <span>Score: {{ att.rust_score }}</span>
                <span>{{ att.timestamp }}</span>
            </div>
            {% endfor %}
        </div>

        <p><a href="/hall-of-fame" style="color: #ff6b35;">← Back to Hall of Fame</a></p>
    </body>
    </html>
    '''

    return render_template_string(html_template, machine=machine, history=history, performance_vs_fleet=performance_vs_fleet)

if __name__ == '__main__':
    app.run(debug=True)
