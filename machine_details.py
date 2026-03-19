// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

from flask import Flask, jsonify, request, render_template_string
import sqlite3
import json
from datetime import datetime, timedelta
import os

app = Flask(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), 'rustchain.db')

def get_machine_details(machine_id):
    """Get comprehensive machine details from database"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get machine basic info
        cursor.execute("""
            SELECT * FROM machines WHERE id = ?
        """, (machine_id,))
        machine = cursor.fetchone()
        
        if not machine:
            return None
            
        # Get latest rust score
        cursor.execute("""
            SELECT rust_score, timestamp FROM rust_scores 
            WHERE machine_id = ? ORDER BY timestamp DESC LIMIT 1
        """, (machine_id,))
        rust_data = cursor.fetchone()
        
        # Get attestation history
        cursor.execute("""
            SELECT * FROM attestations 
            WHERE machine_id = ? ORDER BY timestamp DESC LIMIT 50
        """, (machine_id,))
        attestations = cursor.fetchall()
        
        # Get hardware specs
        cursor.execute("""
            SELECT * FROM hardware_specs WHERE machine_id = ?
        """, (machine_id,))
        hardware = cursor.fetchone()
        
        # Calculate uptime stats
        cursor.execute("""
            SELECT COUNT(*) as total_attestations,
                   MIN(timestamp) as first_seen,
                   MAX(timestamp) as last_seen
            FROM attestations WHERE machine_id = ?
        """, (machine_id,))
        stats = cursor.fetchone()
        
        return {
            'machine': dict(machine),
            'rust_score': dict(rust_data) if rust_data else None,
            'attestations': [dict(row) for row in attestations],
            'hardware': dict(hardware) if hardware else None,
            'stats': dict(stats) if stats else None
        }

def format_timestamp(timestamp):
    """Format timestamp for display"""
    if not timestamp:
        return "N/A"
    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")

def is_machine_deceased(last_seen):
    """Check if machine is considered deceased (no activity for 30+ days)"""
    if not last_seen:
        return False
    last_dt = datetime.fromisoformat(last_seen.replace('Z', '+00:00'))
    return datetime.utcnow() - last_dt > timedelta(days=30)

@app.route('/api/machine/<machine_id>')
def api_machine_details(machine_id):
    """API endpoint for machine details"""
    details = get_machine_details(machine_id)
    if not details:
        return jsonify({'error': 'Machine not found'}), 404
    return jsonify(details)

@app.route('/machine/<machine_id>')
def machine_detail_page(machine_id):
    """Web page for machine details with terminal aesthetic"""
    details = get_machine_details(machine_id)
    if not details:
        return "Machine not found", 404
        
    machine = details['machine']
    rust_score = details['rust_score']
    attestations = details['attestations']
    hardware = details['hardware']
    stats = details['stats']
    
    deceased = is_machine_deceased(stats['last_seen'] if stats else None)
    
    html_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>{{ machine_name }} - Rustchain Machine Profile</title>
        <style>
            body {
                background: #0a0a0a;
                color: #00ff00;
                font-family: 'Courier New', monospace;
                margin: 0;
                padding: 20px;
                line-height: 1.4;
            }
            .container {
                max-width: 1200px;
                margin: 0 auto;
                border: 1px solid #333;
                padding: 20px;
                background: #111;
            }
            .header {
                border-bottom: 1px solid #333;
                padding-bottom: 15px;
                margin-bottom: 20px;
            }
            .machine-name {
                font-size: 24px;
                font-weight: bold;
                {% if deceased %}color: #666; text-decoration: line-through;{% endif %}
            }
            .rust-score {
                font-size: 32px;
                color: #ff6600;
                font-weight: bold;
                text-align: center;
                margin: 20px 0;
                {% if deceased %}opacity: 0.5;{% endif %}
            }
            .section {
                margin: 20px 0;
                border: 1px solid #333;
                padding: 15px;
            }
            .section-title {
                color: #ffff00;
                font-weight: bold;
                margin-bottom: 10px;
                border-bottom: 1px solid #333;
                padding-bottom: 5px;
            }
            .spec-row {
                display: flex;
                justify-content: space-between;
                margin: 5px 0;
            }
            .spec-label {
                color: #00ffff;
            }
            .attestation-row {
                font-size: 12px;
                margin: 2px 0;
                padding: 2px;
                {% if deceased %}opacity: 0.7;{% endif %}
            }
            .deceased-notice {
                background: #2a1a1a;
                border: 2px solid #8b0000;
                padding: 15px;
                margin: 20px 0;
                color: #ff4444;
                text-align: center;
                font-weight: bold;
            }
            .memorial-flame {
                font-size: 20px;
                animation: flicker 2s infinite;
            }
            @keyframes flicker {
                0%, 50%, 100% { opacity: 1; }
                25%, 75% { opacity: 0.7; }
            }
            .back-link {
                color: #00ff00;
                text-decoration: none;
                border: 1px solid #333;
                padding: 5px 10px;
                display: inline-block;
                margin-bottom: 20px;
            }
            .back-link:hover {
                background: #333;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <a href="/leaderboard" class="back-link">← Back to Hall of Fame</a>
            
            {% if deceased %}
            <div class="deceased-notice">
                <span class="memorial-flame">🕯️</span>
                IN MEMORY OF {{ machine_name }}
                <span class="memorial-flame">🕯️</span><br>
                Last seen: {{ format_timestamp(stats.last_seen if stats else None) }}<br>
                Gone but not forgotten in the blockchain
            </div>
            {% endif %}
            
            <div class="header">
                <div class="machine-name">{{ machine_name }}</div>
                <div>Machine ID: {{ machine_id }}</div>
                {% if rust_score %}
                <div class="rust-score">RUST SCORE: {{ "%.2f"|format(rust_score.rust_score) }}</div>
                {% endif %}
            </div>
            
            {% if stats %}
            <div class="section">
                <div class="section-title">SYSTEM STATISTICS</div>
                <div class="spec-row">
                    <span class="spec-label">Total Attestations:</span>
                    <span>{{ stats.total_attestations }}</span>
                </div>
                <div class="spec-row">
                    <span class="spec-label">First Seen:</span>
                    <span>{{ format_timestamp(stats.first_seen) }}</span>
                </div>
                <div class="spec-row">
                    <span class="spec-label">Last Activity:</span>
                    <span>{{ format_timestamp(stats.last_seen) }}</span>
                </div>
                <div class="spec-row">
                    <span class="spec-label">Status:</span>
                    <span>{% if deceased %}DECEASED{% else %}ACTIVE{% endif %}</span>
                </div>
            </div>
            {% endif %}
            
            {% if hardware %}
            <div class="section">
                <div class="section-title">HARDWARE SPECIFICATIONS</div>
                {% if hardware.cpu_model %}
                <div class="spec-row">
                    <span class="spec-label">CPU:</span>
                    <span>{{ hardware.cpu_model }}</span>
                </div>
                {% endif %}
                {% if hardware.memory_gb %}
                <div class="spec-row">
                    <span class="spec-label">Memory:</span>
                    <span>{{ hardware.memory_gb }} GB</span>
                </div>
                {% endif %}
                {% if hardware.storage_gb %}
                <div class="spec-row">
                    <span class="spec-label">Storage:</span>
                    <span>{{ hardware.storage_gb }} GB</span>
                </div>
                {% endif %}
                {% if hardware.os_info %}
                <div class="spec-row">
                    <span class="spec-label">Operating System:</span>
                    <span>{{ hardware.os_info }}</span>
                </div>
                {% endif %}
            </div>
            {% endif %}
            
            <div class="section">
                <div class="section-title">ATTESTATION HISTORY (Latest 50)</div>
                {% for attestation in attestations %}
                <div class="attestation-row">
                    [{{ format_timestamp(attestation.timestamp) }}] 
                    Block: {{ attestation.block_height or 'N/A' }} | 
                    Hash: {{ (attestation.block_hash or 'N/A')[:16] }}... | 
                    Nonce: {{ attestation.nonce or 'N/A' }}
                </div>
                {% endfor %}
                {% if not attestations %}
                <div>No attestation history found</div>
                {% endif %}
            </div>
        </div>
    </body>
    </html>
    """
    
    return render_template_string(
        html_template,
        machine_id=machine_id,
        machine_name=machine.get('name', f'Machine-{machine_id}'),
        machine=machine,
        rust_score=rust_score,
        attestations=attestations,
        hardware=hardware,
        stats=stats,
        deceased=deceased,
        format_timestamp=format_timestamp
    )

if __name__ == '__main__':
    app.run(debug=True)