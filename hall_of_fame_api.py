// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

from flask import Flask, request, jsonify, render_template_string
import sqlite3
import json
from datetime import datetime, timedelta
import os

app = Flask(__name__)

DB_PATH = 'rustchain_network.db'

def get_machine_detail(machine_id):
    """Fetch comprehensive machine data from database"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get machine basic info
        cursor.execute("""
            SELECT * FROM machines WHERE machine_id = ?
        """, (machine_id,))
        machine = cursor.fetchone()
        
        if not machine:
            return None
            
        # Get latest rust score
        cursor.execute("""
            SELECT rust_score, calculation_time, decay_factor, base_score
            FROM rust_calculations 
            WHERE machine_id = ? 
            ORDER BY calculation_time DESC 
            LIMIT 1
        """, (machine_id,))
        rust_data = cursor.fetchone()
        
        # Get attestation history
        cursor.execute("""
            SELECT attestation_type, timestamp, signature, verified
            FROM attestations 
            WHERE machine_id = ? 
            ORDER BY timestamp DESC 
            LIMIT 50
        """, (machine_id,))
        attestations = cursor.fetchall()
        
        # Get hardware specs
        cursor.execute("""
            SELECT cpu_model, cpu_cores, memory_gb, storage_gb, gpu_model
            FROM hardware_specs 
            WHERE machine_id = ?
        """, (machine_id,))
        hardware = cursor.fetchone()
        
        # Get network stats
        cursor.execute("""
            SELECT peers_connected, blocks_processed, uptime_hours
            FROM network_stats 
            WHERE machine_id = ? 
            ORDER BY timestamp DESC 
            LIMIT 1
        """, (machine_id,))
        network = cursor.fetchone()
        
        # Calculate rust score components
        rust_score = rust_data['rust_score'] if rust_data else 0
        uptime_score = (network['uptime_hours'] * 0.1) if network else 0
        attestation_score = len(attestations) * 2.5
        hardware_score = calculate_hardware_score(hardware) if hardware else 0
        
        return {
            'machine_id': machine['machine_id'],
            'node_name': machine['node_name'],
            'status': machine['status'],
            'join_date': machine['join_date'],
            'last_seen': machine['last_seen'],
            'rust_score': {
                'total': rust_score,
                'uptime_component': uptime_score,
                'attestation_component': attestation_score,
                'hardware_component': hardware_score,
                'decay_factor': rust_data['decay_factor'] if rust_data else 1.0
            },
            'attestations': [dict(a) for a in attestations],
            'hardware': dict(hardware) if hardware else {},
            'network_stats': dict(network) if network else {},
            'is_memorial': machine['status'] == 'deceased'
        }

def calculate_hardware_score(hardware):
    """Calculate hardware performance score"""
    if not hardware:
        return 0
        
    score = 0
    score += hardware['cpu_cores'] * 10 if hardware['cpu_cores'] else 0
    score += hardware['memory_gb'] * 0.5 if hardware['memory_gb'] else 0
    score += (hardware['storage_gb'] / 100) if hardware['storage_gb'] else 0
    
    if hardware['gpu_model']:
        score += 50
        
    return min(score, 200)

@app.route('/api/machine/<machine_id>')
def get_machine_api(machine_id):
    """API endpoint for machine details"""
    machine_data = get_machine_detail(machine_id)
    
    if not machine_data:
        return jsonify({'error': 'Machine not found'}), 404
        
    return jsonify(machine_data)

@app.route('/machine/<machine_id>')
def machine_detail_page(machine_id):
    """Machine detail page with terminal aesthetic"""
    machine_data = get_machine_detail(machine_id)
    
    if not machine_data:
        return "Machine not found", 404
        
    memorial_class = "memorial" if machine_data['is_memorial'] else ""
    status_symbol = "💀" if machine_data['is_memorial'] else "🟢" if machine_data['status'] == 'active' else "🔴"
    
    template = """
<!DOCTYPE html>
<html>
<head>
    <title>{{ machine_data.node_name }} - Rustchain Network</title>
    <style>
        body {
            background: #0a0a0a;
            color: #00ff00;
            font-family: 'Courier New', monospace;
            margin: 0;
            padding: 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: #111;
            border: 1px solid #333;
            padding: 20px;
        }
        .header {
            border-bottom: 1px solid #333;
            padding-bottom: 15px;
            margin-bottom: 20px;
        }
        .machine-title {
            font-size: 24px;
            color: #ff6600;
        }
        .memorial {
            color: #666 !important;
            opacity: 0.7;
        }
        .memorial .machine-title {
            color: #888 !important;
        }
        .section {
            margin: 20px 0;
            padding: 15px;
            border: 1px solid #333;
        }
        .section-title {
            color: #ffff00;
            font-size: 18px;
            margin-bottom: 10px;
        }
        .stat-row {
            display: flex;
            justify-content: space-between;
            margin: 5px 0;
        }
        .rust-score {
            font-size: 36px;
            color: #ff6600;
            text-align: center;
            margin: 20px 0;
        }
        .attestation-log {
            max-height: 300px;
            overflow-y: auto;
            background: #000;
            padding: 10px;
            border: 1px solid #333;
        }
        .attestation-entry {
            margin: 5px 0;
            font-size: 12px;
        }
        .verified {
            color: #00ff00;
        }
        .unverified {
            color: #ff0000;
        }
        .back-link {
            color: #00aaff;
            text-decoration: none;
        }
        .back-link:hover {
            text-decoration: underline;
        }
    </style>
</head>
<body>
    <div class="container {{ memorial_class }}">
        <div class="header">
            <a href="/hall_of_fame" class="back-link">← Back to Hall of Fame</a>
            <h1 class="machine-title">{{ status_symbol }} {{ machine_data.node_name }}</h1>
            <p>Machine ID: {{ machine_data.machine_id }}</p>
            <p>Status: {{ machine_data.status.upper() }}</p>
        </div>

        <div class="rust-score">
            RUST SCORE: {{ "%.2f"|format(machine_data.rust_score.total) }}
        </div>

        <div class="section">
            <div class="section-title">RUST SCORE BREAKDOWN</div>
            <div class="stat-row">
                <span>Uptime Component:</span>
                <span>{{ "%.2f"|format(machine_data.rust_score.uptime_component) }}</span>
            </div>
            <div class="stat-row">
                <span>Attestation Component:</span>
                <span>{{ "%.2f"|format(machine_data.rust_score.attestation_component) }}</span>
            </div>
            <div class="stat-row">
                <span>Hardware Component:</span>
                <span>{{ "%.2f"|format(machine_data.rust_score.hardware_component) }}</span>
            </div>
            <div class="stat-row">
                <span>Decay Factor:</span>
                <span>{{ "%.3f"|format(machine_data.rust_score.decay_factor) }}</span>
            </div>
        </div>

        <div class="section">
            <div class="section-title">HARDWARE SPECIFICATIONS</div>
            {% if machine_data.hardware %}
            <div class="stat-row">
                <span>CPU Model:</span>
                <span>{{ machine_data.hardware.cpu_model or "Unknown" }}</span>
            </div>
            <div class="stat-row">
                <span>CPU Cores:</span>
                <span>{{ machine_data.hardware.cpu_cores or "Unknown" }}</span>
            </div>
            <div class="stat-row">
                <span>Memory:</span>
                <span>{{ machine_data.hardware.memory_gb or "Unknown" }} GB</span>
            </div>
            <div class="stat-row">
                <span>Storage:</span>
                <span>{{ machine_data.hardware.storage_gb or "Unknown" }} GB</span>
            </div>
            <div class="stat-row">
                <span>GPU:</span>
                <span>{{ machine_data.hardware.gpu_model or "None" }}</span>
            </div>
            {% else %}
            <p>Hardware information not available</p>
            {% endif %}
        </div>

        <div class="section">
            <div class="section-title">NETWORK STATISTICS</div>
            {% if machine_data.network_stats %}
            <div class="stat-row">
                <span>Connected Peers:</span>
                <span>{{ machine_data.network_stats.peers_connected or 0 }}</span>
            </div>
            <div class="stat-row">
                <span>Blocks Processed:</span>
                <span>{{ machine_data.network_stats.blocks_processed or 0 }}</span>
            </div>
            <div class="stat-row">
                <span>Uptime Hours:</span>
                <span>{{ "%.1f"|format(machine_data.network_stats.uptime_hours or 0) }}</span>
            </div>
            {% else %}
            <p>Network statistics not available</p>
            {% endif %}
        </div>

        <div class="section">
            <div class="section-title">ATTESTATION HISTORY ({{ machine_data.attestations|length }} records)</div>
            <div class="attestation-log">
                {% for attestation in machine_data.attestations %}
                <div class="attestation-entry">
                    <span class="{{ 'verified' if attestation.verified else 'unverified' }}">
                        [{{ attestation.timestamp }}] {{ attestation.attestation_type.upper() }} 
                        {{ "✓" if attestation.verified else "✗" }}
                    </span>
                </div>
                {% endfor %}
                {% if not machine_data.attestations %}
                <p>No attestation records found</p>
                {% endif %}
            </div>
        </div>

        <div class="section">
            <div class="section-title">TIMELINE</div>
            <div class="stat-row">
                <span>Joined Network:</span>
                <span>{{ machine_data.join_date }}</span>
            </div>
            <div class="stat-row">
                <span>Last Seen:</span>
                <span>{{ machine_data.last_seen }}</span>
            </div>
        </div>
    </div>
</body>
</html>
    """
    
    return render_template_string(template, 
                                machine_data=machine_data, 
                                memorial_class=memorial_class,
                                status_symbol=status_symbol)

if __name__ == '__main__':
    app.run(debug=True, port=5001)