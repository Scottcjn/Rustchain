// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

from flask import Flask, request, render_template_string, jsonify
import sqlite3
import json
from datetime import datetime
import os

app = Flask(__name__)
DB_PATH = 'rustchain.db'

def get_machine_detail(machine_id):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        # Get machine basic info
        cursor.execute("""
            SELECT machine_id, rust_score, total_attestations, last_attestation,
                   status, hardware_info, created_at
            FROM machines WHERE machine_id = ?
        """, (machine_id,))
        
        machine = cursor.fetchone()
        if not machine:
            return None
            
        # Get attestation history
        cursor.execute("""
            SELECT timestamp, rust_score, block_hash, attestation_data
            FROM attestations 
            WHERE machine_id = ? 
            ORDER BY timestamp DESC 
            LIMIT 50
        """, (machine_id,))
        
        attestations = cursor.fetchall()
        
        # Get ranking position
        cursor.execute("""
            SELECT COUNT(*) + 1 as rank
            FROM machines 
            WHERE rust_score > (SELECT rust_score FROM machines WHERE machine_id = ?)
        """, (machine_id,))
        
        rank = cursor.fetchone()[0]
        
        return {
            'machine_id': machine[0],
            'rust_score': machine[1],
            'total_attestations': machine[2],
            'last_attestation': machine[3],
            'status': machine[4],
            'hardware_info': json.loads(machine[5]) if machine[5] else {},
            'created_at': machine[6],
            'rank': rank,
            'attestations': [
                {
                    'timestamp': a[0],
                    'rust_score': a[1],
                    'block_hash': a[2],
                    'data': json.loads(a[3]) if a[3] else {}
                }
                for a in attestations
            ]
        }

@app.route('/api/machine/<machine_id>')
def api_machine_detail(machine_id):
    machine = get_machine_detail(machine_id)
    if not machine:
        return jsonify({'error': 'Machine not found'}), 404
    return jsonify(machine)

@app.route('/machine/<machine_id>')
def machine_detail(machine_id):
    machine = get_machine_detail(machine_id)
    if not machine:
        return "Machine not found", 404
        
    is_deceased = machine['status'] == 'inactive'
    last_seen = datetime.fromisoformat(machine['last_attestation']).strftime('%Y-%m-%d %H:%M:%S') if machine['last_attestation'] else 'Never'
    created = datetime.fromisoformat(machine['created_at']).strftime('%Y-%m-%d %H:%M:%S')
    
    hardware = machine['hardware_info']
    
    template = """
<!DOCTYPE html>
<html>
<head>
    <title>{{ machine_id }} - Rustchain Hall of Fame</title>
    <style>
        body {
            background: #000;
            color: #00ff00;
            font-family: 'Courier New', monospace;
            margin: 0;
            padding: 20px;
            line-height: 1.4;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        
        .header {
            border: 2px solid #00ff00;
            padding: 20px;
            margin-bottom: 20px;
            {% if is_deceased %}
            border-color: #ff0000;
            background: rgba(255, 0, 0, 0.1);
            {% endif %}
        }
        
        .machine-id {
            font-size: 24px;
            font-weight: bold;
            margin-bottom: 10px;
            {% if is_deceased %}
            color: #ff0000;
            {% endif %}
        }
        
        .status-badge {
            display: inline-block;
            padding: 5px 15px;
            border: 1px solid;
            margin: 5px 0;
            {% if is_deceased %}
            border-color: #ff0000;
            color: #ff0000;
            {% else %}
            border-color: #00ff00;
            color: #00ff00;
            {% endif %}
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .stat-block {
            border: 1px solid #00ff00;
            padding: 15px;
            {% if is_deceased %}
            border-color: #666;
            color: #888;
            {% endif %}
        }
        
        .stat-title {
            color: #ffff00;
            font-weight: bold;
            margin-bottom: 10px;
            {% if is_deceased %}
            color: #999;
            {% endif %}
        }
        
        .rust-score {
            font-size: 36px;
            font-weight: bold;
            color: #ff6600;
            {% if is_deceased %}
            color: #664422;
            {% endif %}
        }
        
        .attestations-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
            {% if is_deceased %}
            opacity: 0.6;
            {% endif %}
        }
        
        .attestations-table th,
        .attestations-table td {
            border: 1px solid #00ff00;
            padding: 8px;
            text-align: left;
            {% if is_deceased %}
            border-color: #666;
            {% endif %}
        }
        
        .attestations-table th {
            background: rgba(0, 255, 0, 0.2);
            {% if is_deceased %}
            background: rgba(100, 100, 100, 0.2);
            {% endif %}
        }
        
        .back-link {
            color: #00ff00;
            text-decoration: none;
            border: 1px solid #00ff00;
            padding: 10px 20px;
            display: inline-block;
            margin-bottom: 20px;
        }
        
        .back-link:hover {
            background: rgba(0, 255, 0, 0.2);
        }
        
        .memorial {
            text-align: center;
            color: #ff0000;
            font-size: 18px;
            margin: 20px 0;
            animation: blink 2s infinite;
        }
        
        @keyframes blink {
            0%, 50% { opacity: 1; }
            51%, 100% { opacity: 0.3; }
        }
        
        .hardware-spec {
            margin: 5px 0;
        }
        
        .block-hash {
            font-family: monospace;
            font-size: 12px;
            color: #666;
        }
    </style>
</head>
<body>
    <div class="container">
        <a href="/hall-of-fame" class="back-link">← Back to Hall of Fame</a>
        
        {% if is_deceased %}
        <div class="memorial">⚠️ MACHINE DECEASED - NO RECENT ACTIVITY ⚠️</div>
        {% endif %}
        
        <div class="header">
            <div class="machine-id">{{ machine_id }}</div>
            <div class="status-badge">{{ status.upper() }}</div>
            <div>Rank #{{ rank }} in Hall of Fame</div>
        </div>
        
        <div class="stats-grid">
            <div class="stat-block">
                <div class="stat-title">RUST SCORE</div>
                <div class="rust-score">{{ "%.2f"|format(rust_score) }}</div>
            </div>
            
            <div class="stat-block">
                <div class="stat-title">ATTESTATIONS</div>
                <div>Total: {{ total_attestations }}</div>
                <div>Last: {{ last_seen }}</div>
            </div>
            
            <div class="stat-block">
                <div class="stat-title">MACHINE LIFECYCLE</div>
                <div>Created: {{ created }}</div>
                <div>Status: {{ status }}</div>
            </div>
            
            <div class="stat-block">
                <div class="stat-title">HARDWARE PROFILE</div>
                {% for key, value in hardware.items() %}
                <div class="hardware-spec">{{ key }}: {{ value }}</div>
                {% endfor %}
                {% if not hardware %}
                <div>Hardware info not available</div>
                {% endif %}
            </div>
        </div>
        
        <div class="stat-block">
            <div class="stat-title">ATTESTATION HISTORY</div>
            {% if attestations %}
            <table class="attestations-table">
                <tr>
                    <th>Timestamp</th>
                    <th>Rust Score</th>
                    <th>Block Hash</th>
                    <th>Data</th>
                </tr>
                {% for att in attestations %}
                <tr>
                    <td>{{ att.timestamp }}</td>
                    <td>{{ "%.2f"|format(att.rust_score) }}</td>
                    <td class="block-hash">{{ att.block_hash[:16] }}...</td>
                    <td>{{ att.data.keys()|list|join(', ') if att.data else 'N/A' }}</td>
                </tr>
                {% endfor %}
            </table>
            {% else %}
            <div>No attestation history available</div>
            {% endif %}
        </div>
    </div>
</body>
</html>
"""
    
    return render_template_string(template, 
                                machine_id=machine['machine_id'],
                                rust_score=machine['rust_score'],
                                total_attestations=machine['total_attestations'],
                                last_seen=last_seen,
                                status=machine['status'],
                                rank=machine['rank'],
                                created=created,
                                hardware=hardware,
                                attestations=machine['attestations'],
                                is_deceased=is_deceased)

if __name__ == '__main__':
    app.run(debug=True, port=5003)