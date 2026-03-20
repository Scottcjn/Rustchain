# SPDX-License-Identifier: MIT

from flask import Flask, request, render_template_string
import sqlite3
from datetime import datetime, timezone
import hashlib

DB_PATH = 'rustchain.db'

def get_machine_detail_page():
    """Hall of Fame machine detail page with CRT terminal aesthetic"""

    machine_id = request.args.get('id', '').strip()
    if not machine_id:
        return render_template_string(MACHINE_ERROR_TEMPLATE,
                                    error="Machine ID required")

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get machine details with attestation history
        cursor.execute("""
            SELECT
                m.fingerprint_hash,
                m.machine_name,
                m.rust_score,
                m.total_epochs,
                m.first_seen,
                m.last_seen,
                m.status,
                m.hardware_info,
                COUNT(a.id) as attestation_count,
                AVG(a.rust_delta) as avg_rust_delta,
                MIN(a.created_at) as first_attestation,
                MAX(a.created_at) as latest_attestation
            FROM machines m
            LEFT JOIN attestations a ON m.fingerprint_hash = a.machine_fingerprint
            WHERE m.fingerprint_hash = ?
            GROUP BY m.fingerprint_hash
        """, (machine_id,))

        machine = cursor.fetchone()
        if not machine:
            return render_template_string(MACHINE_ERROR_TEMPLATE,
                                        error="Machine not found")

        # Get recent attestation history for timeline
        cursor.execute("""
            SELECT created_at, rust_delta, epoch_number, block_height
            FROM attestations
            WHERE machine_fingerprint = ?
            ORDER BY created_at DESC
            LIMIT 20
        """, (machine_id,))

        recent_attestations = cursor.fetchall()

        # Calculate fleet averages for comparison
        cursor.execute("""
            SELECT
                AVG(rust_score) as fleet_avg_score,
                AVG(total_epochs) as fleet_avg_epochs,
                COUNT(*) as total_machines
            FROM machines
            WHERE status = 'active'
        """)

        fleet_stats = cursor.fetchone()

        # Generate machine silhouette based on fingerprint
        silhouette = generate_ascii_silhouette(machine['fingerprint_hash'])

        # Determine if machine is deceased
        is_deceased = machine['status'] == 'inactive'

        # Calculate rust score badge
        rust_badge = get_rust_badge(machine['rust_score'])

        return render_template_string(
            MACHINE_DETAIL_TEMPLATE,
            machine=dict(machine),
            recent_attestations=[dict(row) for row in recent_attestations],
            fleet_stats=dict(fleet_stats) if fleet_stats else {},
            silhouette=silhouette,
            is_deceased=is_deceased,
            rust_badge=rust_badge,
            current_time=datetime.now(timezone.utc).isoformat()
        )

def generate_ascii_silhouette(fingerprint_hash):
    """Generate ASCII art machine silhouette based on fingerprint hash"""

    # Use hash to determine machine type silhouette
    hash_int = int(fingerprint_hash[:8], 16) if fingerprint_hash else 0
    machine_type = hash_int % 4

    silhouettes = {
        0: """
    ╔═══════════════╗
    ║   ████  ████  ║
    ║   ████  ████  ║
    ║               ║
    ║  ███████████  ║
    ║  ███████████  ║
    ╚═══════════════╝
        """,
        1: """
    ┌─────────────────┐
    │ ▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄ │
    │ █░░░░░░░░░░░░░█ │
    │ █░██░░██░░██░█ │
    │ █░░░░░░░░░░░░░█ │
    │ ▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀ │
    └─────────────────┘
        """,
        2: """
    ╭─────────────────╮
    │  ▲▲▲  ▲▲▲  ▲▲▲  │
    │ ████ ████ ████  │
    │ ▼▼▼▼ ▼▼▼▼ ▼▼▼▼  │
    │                 │
    │ =============== │
    ╰─────────────────╯
        """,
        3: """
        ╔═══╗
        ║▓▓▓║
    ╔═══╩═══╩═══╗
    ║ ░░░░░░░░░ ║
    ║ ░██░░██░ ║
    ║ ░░░░░░░░░ ║
    ╚═══════════╝
        """
    }

    return silhouettes.get(machine_type, silhouettes[0])

def get_rust_badge(rust_score):
    """Generate rust score badge styling"""
    if rust_score >= 900:
        return {'class': 'legendary', 'text': 'LEGENDARY'}
    elif rust_score >= 750:
        return {'class': 'elite', 'text': 'ELITE'}
    elif rust_score >= 500:
        return {'class': 'veteran', 'text': 'VETERAN'}
    elif rust_score >= 250:
        return {'class': 'active', 'text': 'ACTIVE'}
    else:
        return {'class': 'rookie', 'text': 'ROOKIE'}

MACHINE_DETAIL_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ machine.machine_name or machine.fingerprint_hash[:8] }} - Hall of Fame</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono:wght@400&display=swap');

        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: 'Share Tech Mono', monospace;
            background: #0a0a0a;
            color: #00ff41;
            line-height: 1.4;
            overflow-x: auto;
        }

        .terminal {
            background: radial-gradient(ellipse at center, #001100 0%, #000000 100%);
            min-height: 100vh;
            padding: 20px;
            position: relative;
        }

        .terminal::before {
            content: '';
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: repeating-linear-gradient(
                0deg,
                transparent,
                transparent 2px,
                rgba(0, 255, 65, 0.03) 2px,
                rgba(0, 255, 65, 0.03) 4px
            );
            pointer-events: none;
            z-index: 1;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
            position: relative;
            z-index: 2;
        }

        .header {
            text-align: center;
            margin-bottom: 30px;
            padding: 20px;
            border: 1px solid #00ff41;
            background: rgba(0, 255, 65, 0.05);
        }

        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
            text-shadow: 0 0 10px #00ff41;
            {% if is_deceased %}
            color: #ff4444;
            text-shadow: 0 0 10px #ff4444;
            {% endif %}
        }

        .machine-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
            margin-bottom: 30px;
        }

        @media (max-width: 768px) {
            .machine-grid { grid-template-columns: 1fr; }
        }

        .machine-card {
            border: 1px solid #00ff41;
            padding: 20px;
            background: rgba(0, 255, 65, 0.02);
            {% if is_deceased %}
            border-color: #ff4444;
            background: rgba(255, 68, 68, 0.02);
            {% endif %}
        }

        .silhouette {
            text-align: center;
            margin: 20px 0;
            white-space: pre;
            font-size: 0.8em;
            {% if is_deceased %}
            color: #888;
            opacity: 0.6;
            {% endif %}
        }

        .rust-badge {
            display: inline-block;
            padding: 5px 15px;
            margin: 10px 0;
            border: 2px solid;
            font-weight: bold;
            text-align: center;
        }

        .rust-badge.legendary {
            color: #ffd700;
            border-color: #ffd700;
            text-shadow: 0 0 5px #ffd700;
        }
        .rust-badge.elite {
            color: #ff6600;
            border-color: #ff6600;
        }
        .rust-badge.veteran {
            color: #00ff41;
            border-color: #00ff41;
        }
        .rust-badge.active {
            color: #00aaff;
            border-color: #00aaff;
        }
        .rust-badge.rookie {
            color: #888;
            border-color: #888;
        }

        .stats-row {
            display: flex;
            justify-content: space-between;
            margin: 10px 0;
            padding: 5px 0;
            border-bottom: 1px dotted #444;
        }

        .timeline {
            margin-top: 30px;
        }

        .timeline h3 {
            margin-bottom: 15px;
            color: #00ff41;
            {% if is_deceased %}
            color: #ff4444;
            {% endif %}
        }

        .attestation-entry {
            padding: 8px;
            margin: 5px 0;
            border-left: 3px solid #00ff41;
            background: rgba(0, 255, 65, 0.05);
            {% if is_deceased %}
            border-left-color: #ff4444;
            background: rgba(255, 68, 68, 0.05);
            {% endif %}
        }

        .back-link {
            color: #00ff41;
            text-decoration: none;
            padding: 10px;
            border: 1px solid #00ff41;
            display: inline-block;
            margin-bottom: 20px;
        }

        .back-link:hover {
            background: rgba(0, 255, 65, 0.1);
        }

        .deceased-memorial {
            text-align: center;
            padding: 20px;
            margin: 20px 0;
            border: 2px solid #ff4444;
            background: rgba(255, 68, 68, 0.1);
            color: #ff4444;
        }

        .fleet-comparison {
            margin-top: 20px;
            padding: 15px;
            border: 1px dashed #666;
            background: rgba(255, 255, 255, 0.02);
        }
    </style>
</head>
<body>
    <div class="terminal">
        <div class="container">
            <a href="/hall-of-fame/" class="back-link">← Back to Hall of Fame</a>

            <div class="header">
                <h1>{{ machine.machine_name or 'MACHINE-' + machine.fingerprint_hash[:8] }}</h1>
                <div>Fingerprint: {{ machine.fingerprint_hash }}</div>
                {% if is_deceased %}
                <div class="deceased-memorial">
                    ⚰️ DECOMMISSIONED ⚰️<br>
                    This machine has ceased operations<br>
                    Last seen: {{ machine.last_seen }}
                </div>
                {% endif %}
            </div>

            <div class="machine-grid">
                <div class="machine-card">
                    <h3>MACHINE PROFILE</h3>

                    <div class="silhouette">{{ silhouette }}</div>

                    <div class="rust-badge {{ rust_badge.class }}">
                        {{ rust_badge.text }} - {{ machine.rust_score }} RTC
                    </div>

                    <div class="stats-row">
                        <span>Total Epochs:</span>
                        <span>{{ machine.total_epochs }}</span>
                    </div>

                    <div class="stats-row">
                        <span>First Seen:</span>
                        <span>{{ machine.first_seen }}</span>
                    </div>

                    <div class="stats-row">
                        <span>Last Seen:</span>
                        <span>{{ machine.last_seen }}</span>
                    </div>

                    <div class="stats-row">
                        <span>Status:</span>
                        <span>{{ machine.status.upper() }}</span>
                    </div>

                    <div class="stats-row">
                        <span>Attestations:</span>
                        <span>{{ machine.attestation_count }}</span>
                    </div>

                    {% if machine.avg_rust_delta %}
                    <div class="stats-row">
                        <span>Avg Rust Delta:</span>
                        <span>{{ "%.2f"|format(machine.avg_rust_delta) }}</span>
                    </div>
                    {% endif %}
                </div>

                <div class="machine-card">
                    <h3>FLEET COMPARISON</h3>

                    {% if fleet_stats.fleet_avg_score %}
                    <div class="stats-row">
                        <span>Your Score:</span>
                        <span>{{ machine.rust_score }} RTC</span>
                    </div>

                    <div class="stats-row">
                        <span>Fleet Average:</span>
                        <span>{{ "%.1f"|format(fleet_stats.fleet_avg_score) }} RTC</span>
                    </div>

                    <div class="stats-row">
                        <span>Performance:</span>
                        <span>
                            {% set diff = machine.rust_score - fleet_stats.fleet_avg_score %}
                            {% if diff > 0 %}
                                +{{ "%.1f"|format(diff) }} above avg
                            {% else %}
                                {{ "%.1f"|format(diff) }} below avg
                            {% endif %}
                        </span>
                    </div>

                    <div class="stats-row">
                        <span>Your Epochs:</span>
                        <span>{{ machine.total_epochs }}</span>
                    </div>

                    <div class="stats-row">
                        <span>Fleet Avg Epochs:</span>
                        <span>{{ "%.1f"|format(fleet_stats.fleet_avg_epochs) }}</span>
                    </div>

                    <div class="stats-row">
                        <span>Total Fleet:</span>
                        <span>{{ fleet_stats.total_machines }} machines</span>
                    </div>
                    {% else %}
                    <div>Fleet statistics unavailable</div>
                    {% endif %}

                    {% if machine.hardware_info %}
                    <div class="fleet-comparison">
                        <strong>Hardware Info:</strong><br>
                        {{ machine.hardware_info }}
                    </div>
                    {% endif %}
                </div>
            </div>

            <div class="timeline">
                <h3>RECENT ATTESTATION HISTORY</h3>

                {% if recent_attestations %}
                    {% for att in recent_attestations %}
                    <div class="attestation-entry">
                        <strong>{{ att.created_at }}</strong> -
                        Epoch {{ att.epoch_number }} -
                        Block {{ att.block_height }} -
                        Rust Delta: {{ att.rust_delta }}
                    </div>
                    {% endfor %}
                {% else %}
                    <div class="attestation-entry">
                        No attestation history found
                    </div>
                {% endif %}
            </div>

            <div style="text-align: center; margin-top: 40px; color: #555;">
                Generated at {{ current_time }}
            </div>
        </div>
    </div>
</body>
</html>
"""

MACHINE_ERROR_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Machine Not Found - Hall of Fame</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono:wght@400&display=swap');

        body {
            font-family: 'Share Tech Mono', monospace;
            background: #0a0a0a;
            color: #ff4444;
            text-align: center;
            padding: 50px;
        }

        .error-box {
            border: 2px solid #ff4444;
            padding: 40px;
            max-width: 500px;
            margin: 0 auto;
            background: rgba(255, 68, 68, 0.1);
        }

        .back-link {
            color: #00ff41;
            text-decoration: none;
            padding: 10px;
            border: 1px solid #00ff41;
            display: inline-block;
            margin-top: 20px;
        }

        .back-link:hover {
            background: rgba(0, 255, 65, 0.1);
        }
    </style>
</head>
<body>
    <div class="error-box">
        <h1>ERROR</h1>
        <p>{{ error }}</p>
        <a href="/hall-of-fame/" class="back-link">← Back to Hall of Fame</a>
    </div>
</body>
</html>
"""
