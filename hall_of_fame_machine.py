// SPDX-License-Identifier: MIT
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
    if history:
        recent_scores = [h['rust_score'] for h in history[:10]]
        trend = "RISING" if len(recent_scores) > 1 and recent_scores[0] > recent_scores[-1] else "STABLE"
        avg_recent = sum(recent_scores) / len(recent_scores)
    else:
        trend = "NO_DATA"
        avg_recent = 0

    html_template = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ machine.machine_name or machine.fingerprint_hash[:12] }} - Hall of Fame</title>
    <style>
        body {
            font-family: 'Courier New', monospace;
            background: #0a0a0a;
            color: #00ff41;
            margin: 0;
            padding: 20px;
            line-height: 1.4;
        }
        .terminal-container {
            max-width: 1200px;
            margin: 0 auto;
            background: #111;
            border: 2px solid #333;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 0 20px rgba(0, 255, 65, 0.3);
        }
        .header {
            border-bottom: 2px solid #333;
            padding-bottom: 15px;
            margin-bottom: 20px;
        }
        .machine-title {
            font-size: 1.5em;
            color: #fff;
            margin-bottom: 5px;
        }
        .machine-hash {
            color: #888;
            font-size: 0.9em;
            font-family: monospace;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-box {
            background: #1a1a1a;
            border: 1px solid #333;
            padding: 15px;
            border-radius: 4px;
        }
        .stat-label {
            color: #aaa;
            font-size: 0.9em;
            margin-bottom: 5px;
        }
        .stat-value {
            font-size: 1.3em;
            font-weight: bold;
            color: #00ff41;
        }
        .trend-up { color: #00ff41; }
        .trend-stable { color: #ffaa00; }
        .history-section {
            margin-top: 30px;
        }
        .section-title {
            font-size: 1.2em;
            color: #fff;
            border-bottom: 1px solid #333;
            padding-bottom: 10px;
            margin-bottom: 15px;
        }
        .history-table {
            width: 100%;
            border-collapse: collapse;
            background: #1a1a1a;
        }
        .history-table th,
        .history-table td {
            padding: 10px;
            text-align: left;
            border-bottom: 1px solid #333;
        }
        .history-table th {
            background: #2a2a2a;
            color: #fff;
        }
        .back-link {
            color: #00ff41;
            text-decoration: none;
            margin-bottom: 20px;
            display: inline-block;
        }
        .back-link:hover {
            text-decoration: underline;
        }
        .performance-indicator {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 3px;
            font-size: 0.8em;
            margin-left: 10px;
        }
        .perf-above { background: #2d5a2d; color: #00ff41; }
        .perf-below { background: #5a2d2d; color: #ff4444; }
        @media (max-width: 768px) {
            .stats-grid {
                grid-template-columns: 1fr;
            }
            .terminal-container {
                padding: 15px;
                margin: 10px;
            }
        }
    </style>
</head>
<body>
    <div class="terminal-container">
        <a href="/hall-of-fame" class="back-link">&lt; Back to Hall of Fame</a>

        <div class="header">
            <div class="machine-title">
                {{ machine.machine_name or 'Machine #' + machine.fingerprint_hash[:8] }}
            </div>
            <div class="machine-hash">{{ machine.fingerprint_hash }}</div>
        </div>

        <div class="stats-grid">
            <div class="stat-box">
                <div class="stat-label">Rust Score</div>
                <div class="stat-value">
                    {{ "%.2f"|format(machine.rust_score) }}
                    {% if avg_recent > fleet_stats.avg_score %}
                        <span class="performance-indicator perf-above">ABOVE FLEET AVG</span>
                    {% else %}
                        <span class="performance-indicator perf-below">BELOW FLEET AVG</span>
                    {% endif %}
                </div>
            </div>

            <div class="stat-box">
                <div class="stat-label">Fleet Rank</div>
                <div class="stat-value">#{{ machine.fleet_rank }} / {{ fleet_stats.total_machines }}</div>
            </div>

            <div class="stat-box">
                <div class="stat-label">Total Attestations</div>
                <div class="stat-value">{{ machine.total_attestations }}</div>
            </div>

            <div class="stat-box">
                <div class="stat-label">First Seen</div>
                <div class="stat-value">{{ machine.first_seen.split('T')[0] if machine.first_seen else 'Unknown' }}</div>
            </div>

            <div class="stat-box">
                <div class="stat-label">Performance Trend</div>
                <div class="stat-value trend-{{ trend.lower() }}">{{ trend }}</div>
            </div>

            <div class="stat-box">
                <div class="stat-label">Fleet Average</div>
                <div class="stat-value">{{ "%.2f"|format(fleet_stats.avg_score) }}</div>
            </div>
        </div>

        {% if history %}
        <div class="history-section">
            <div class="section-title">Recent Attestation History</div>
            <table class="history-table">
                <thead>
                    <tr>
                        <th>Epoch</th>
                        <th>Rust Score</th>
                        <th>Timestamp</th>
                        <th>Variance</th>
                    </tr>
                </thead>
                <tbody>
                    {% for h in history %}
                    <tr>
                        <td>{{ h.epoch }}</td>
                        <td>{{ "%.2f"|format(h.rust_score) }}</td>
                        <td>{{ h.timestamp.split('T')[0] if h.timestamp else 'N/A' }}</td>
                        <td>
                            {% set variance = h.rust_score - fleet_stats.avg_score %}
                            {% if variance > 0 %}
                                <span class="trend-up">+{{ "%.2f"|format(variance) }}</span>
                            {% else %}
                                <span class="trend-stable">{{ "%.2f"|format(variance) }}</span>
                            {% endif %}
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        {% endif %}
    </div>
</body>
</html>
    '''

    return render_template_string(html_template,
                                machine=machine,
                                history=history,
                                fleet_stats=fleet_stats,
                                trend=trend,
                                avg_recent=avg_recent)

@app.route('/api/hall_of_fame/machine')
def api_machine_detail():
    machine_id = request.args.get('id')
    if not machine_id:
        return jsonify({'error': 'Machine ID required'}), 400

    machine_data = get_machine_details(machine_id)
    if not machine_data:
        return jsonify({'error': 'Machine not found'}), 404

    # Add calculated metrics to response
    history = machine_data['attestation_history']
    if history:
        recent_scores = [h['rust_score'] for h in history[:10]]
        machine_data['performance_metrics'] = {
            'recent_average': sum(recent_scores) / len(recent_scores),
            'trend': 'rising' if len(recent_scores) > 1 and recent_scores[0] > recent_scores[-1] else 'stable',
            'variance_from_fleet': recent_scores[0] - machine_data['fleet_stats']['avg_score'] if recent_scores else 0
        }

    return jsonify(machine_data)

if __name__ == '__main__':
    app.run(debug=True)
