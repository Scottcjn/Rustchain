# SPDX-License-Identifier: MIT

import sqlite3
import os
from flask import Flask, request, render_template_string
from datetime import datetime
import json

DB_PATH = 'rustchain.db'

def get_machine_details(fingerprint_hash):
    """Get detailed information for a specific machine"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        # Get basic machine info
        cursor.execute('''
            SELECT fingerprint, rust_score, epochs_participated,
                   first_attested, last_attested, machine_name
            FROM machines
            WHERE fingerprint = ?
        ''', (fingerprint_hash,))

        machine_data = cursor.fetchone()
        if not machine_data:
            return None

        # Get attestation history
        cursor.execute('''
            SELECT timestamp, rust_score, epoch_number
            FROM attestations
            WHERE machine_fingerprint = ?
            ORDER BY timestamp DESC
            LIMIT 50
        ''', (fingerprint_hash,))

        attestation_history = cursor.fetchall()

        # Get fleet average for comparison
        cursor.execute('SELECT AVG(rust_score) FROM machines WHERE rust_score > 0')
        fleet_avg = cursor.fetchone()[0] or 0

        return {
            'fingerprint': machine_data[0],
            'rust_score': machine_data[1],
            'epochs_participated': machine_data[2],
            'first_attested': machine_data[3],
            'last_attested': machine_data[4],
            'machine_name': machine_data[5] or f"Machine-{fingerprint_hash[:8]}",
            'attestation_history': attestation_history,
            'fleet_average': fleet_avg
        }

def get_hall_of_fame_data():
    """Get the main hall of fame leaderboard data"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT fingerprint, rust_score, epochs_participated,
                   machine_name, last_attested
            FROM machines
            WHERE rust_score > 0
            ORDER BY rust_score DESC, epochs_participated DESC
            LIMIT 50
        ''')
        return cursor.fetchall()

app = Flask(__name__)

@app.route('/hall-of-fame-enhanced')
def hall_of_fame_enhanced():
    machine_id = request.args.get('machine')

    if machine_id:
        # Show machine detail page
        machine_details = get_machine_details(machine_id)
        if not machine_details:
            return "Machine not found", 404

        template = '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>{{ machine_name }} - Rustchain Hall of Fame</title>
            <style>
                body { font-family: 'Courier New', monospace; background: #0a0a0a; color: #00ff00; margin: 0; padding: 20px; }
                .container { max-width: 1200px; margin: 0 auto; }
                .header { text-align: center; margin-bottom: 30px; }
                .machine-card { background: #1a1a1a; border: 2px solid #00ff00; padding: 20px; margin: 20px 0; }
                .stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 15px; margin: 20px 0; }
                .stat-box { background: #0f0f0f; border: 1px solid #00aa00; padding: 15px; text-align: center; }
                .history-table { width: 100%; border-collapse: collapse; margin: 20px 0; }
                .history-table th, .history-table td { border: 1px solid #00aa00; padding: 8px; text-align: left; }
                .back-link { color: #00ff00; text-decoration: none; }
                .back-link:hover { text-decoration: underline; }
                .comparison { margin: 15px 0; padding: 10px; background: #1a1a1a; }
                .better { color: #00ff00; }
                .worse { color: #ff6600; }
                .chart-container { margin: 20px 0; height: 200px; background: #0f0f0f; border: 1px solid #00aa00; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🏆 {{ machine_name }}</h1>
                    <p><a href="/hall-of-fame-enhanced" class="back-link">← Back to Hall of Fame</a></p>
                </div>

                <div class="machine-card">
                    <h2>Machine Profile</h2>
                    <p><strong>Fingerprint:</strong> {{ fingerprint }}</p>

                    <div class="stat-grid">
                        <div class="stat-box">
                            <h3>Rust Score</h3>
                            <div style="font-size: 24px;">{{ "%.2f"|format(rust_score) }}</div>
                        </div>
                        <div class="stat-box">
                            <h3>Epochs Participated</h3>
                            <div style="font-size: 24px;">{{ epochs_participated }}</div>
                        </div>
                        <div class="stat-box">
                            <h3>First Attested</h3>
                            <div>{{ first_attested }}</div>
                        </div>
                        <div class="stat-box">
                            <h3>Last Attested</h3>
                            <div>{{ last_attested }}</div>
                        </div>
                    </div>

                    <div class="comparison">
                        <h3>Fleet Comparison</h3>
                        <p>Your Score: {{ "%.2f"|format(rust_score) }} |
                        Fleet Average: {{ "%.2f"|format(fleet_average) }} |
                        <span class="{{ 'better' if rust_score > fleet_average else 'worse' }}">
                            {{ "%.1f%"|format(((rust_score / fleet_average - 1) * 100) if fleet_average > 0 else 0) }} vs average
                        </span></p>
                    </div>
                </div>

                <div class="machine-card">
                    <h2>Recent Attestation History</h2>
                    <table class="history-table">
                        <thead>
                            <tr>
                                <th>Timestamp</th>
                                <th>Epoch</th>
                                <th>Rust Score</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for attestation in attestation_history[:10] %}
                            <tr>
                                <td>{{ attestation[0] }}</td>
                                <td>{{ attestation[2] or 'N/A' }}</td>
                                <td>{{ "%.2f"|format(attestation[1]) }}</td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
        </body>
        </html>
        '''

        return render_template_string(template, **machine_details)

    else:
        # Show main hall of fame with clickable links
        machines = get_hall_of_fame_data()

        template = '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Hall of Fame - Rustchain</title>
            <style>
                body { font-family: 'Courier New', monospace; background: #0a0a0a; color: #00ff00; margin: 0; padding: 20px; }
                .container { max-width: 1200px; margin: 0 auto; }
                .header { text-align: center; margin-bottom: 30px; }
                .leaderboard { background: #1a1a1a; border: 2px solid #00ff00; padding: 20px; }
                .machine-row { display: grid; grid-template-columns: 50px 200px 100px 100px 150px; gap: 15px; padding: 10px; border-bottom: 1px solid #003300; align-items: center; }
                .machine-row:hover { background: #0f0f0f; cursor: pointer; }
                .machine-link { color: #00ff00; text-decoration: none; display: contents; }
                .machine-link:hover { color: #66ff66; }
                .rank { font-weight: bold; text-align: center; }
                .fingerprint { font-family: monospace; font-size: 12px; }
                .score { font-weight: bold; color: #ffaa00; }
                .header-row { font-weight: bold; border-bottom: 2px solid #00ff00; background: #0f0f0f; }
                .trophy { font-size: 18px; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🏆 RUSTCHAIN HALL OF FAME 🏆</h1>
                    <p>Click on any machine to view detailed profile</p>
                </div>

                <div class="leaderboard">
                    <div class="machine-row header-row">
                        <div class="rank">Rank</div>
                        <div>Machine</div>
                        <div>Rust Score</div>
                        <div>Epochs</div>
                        <div>Last Active</div>
                    </div>

                    {% for i, machine in enumerate(machines) %}
                    <a href="?machine={{ machine[0] }}" class="machine-link">
                        <div class="machine-row">
                            <div class="rank">
                                {{ i + 1 }}
                                {% if i == 0 %}🥇{% elif i == 1 %}🥈{% elif i == 2 %}🥉{% endif %}
                            </div>
                            <div>
                                <div><strong>{{ machine[3] or ('Machine-' + machine[0][:8]) }}</strong></div>
                                <div class="fingerprint">{{ machine[0][:16] }}...</div>
                            </div>
                            <div class="score">{{ "%.2f"|format(machine[1]) }}</div>
                            <div>{{ machine[2] }}</div>
                            <div>{{ machine[4][:10] if machine[4] else 'N/A' }}</div>
                        </div>
                    </a>
                    {% endfor %}
                </div>

                <div style="text-align: center; margin-top: 20px; color: #666;">
                    <p>🔗 Enhanced Hall of Fame - Click machines for detailed profiles</p>
                </div>
            </div>
        </body>
        </html>
        '''

        return render_template_string(template, machines=machines, enumerate=enumerate)

if __name__ == '__main__':
    app.run(debug=True)
