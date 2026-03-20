// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

from flask import Flask, render_template_string
from flask_cors import CORS
import sqlite3
import requests
import json
from datetime import datetime, timedelta
import threading
import time
import os

app = Flask(__name__)
CORS(app)

DB_PATH = 'multi_node_health.db'

# Node configurations
NODES = {
    'node1': {
        'name': 'Primary Node',
        'url': 'https://50.28.86.131/health',
        'role': 'Primary'
    },
    'node2': {
        'name': 'Secondary Node',
        'url': 'https://50.28.86.153/health',
        'role': 'Secondary'
    },
    'node3': {
        'name': 'External Node',
        'url': 'http://100.88.109.32:8099/health',
        'role': 'External (Tailscale)'
    }
}

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS node_health (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                status TEXT NOT NULL,
                response_data TEXT,
                response_time REAL
            )
        ''')
        conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_node_timestamp
            ON node_health(node_id, timestamp)
        ''')

def fetch_node_health(node_id, config):
    try:
        start_time = time.time()
        response = requests.get(config['url'], timeout=10, verify=False)
        response_time = time.time() - start_time

        if response.status_code == 200:
            data = response.json()
            status = 'up'
        else:
            data = {'error': f'HTTP {response.status_code}'}
            status = 'degraded'

    except Exception as e:
        data = {'error': str(e)}
        status = 'down'
        response_time = 10.0

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            INSERT INTO node_health (node_id, timestamp, status, response_data, response_time)
            VALUES (?, ?, ?, ?, ?)
        ''', (node_id, int(time.time()), status, json.dumps(data), response_time))

    return status, data, response_time

def health_monitor():
    while True:
        for node_id, config in NODES.items():
            fetch_node_health(node_id, config)
        time.sleep(30)

def get_latest_health():
    health_data = {}

    with sqlite3.connect(DB_PATH) as conn:
        for node_id in NODES.keys():
            cursor = conn.execute('''
                SELECT status, response_data, response_time, timestamp
                FROM node_health
                WHERE node_id = ?
                ORDER BY timestamp DESC LIMIT 1
            ''', (node_id,))

            row = cursor.fetchone()
            if row:
                status, response_data, response_time, timestamp = row
                try:
                    data = json.loads(response_data)
                except:
                    data = {}

                health_data[node_id] = {
                    'status': status,
                    'data': data,
                    'response_time': response_time,
                    'last_check': timestamp
                }
            else:
                health_data[node_id] = {
                    'status': 'unknown',
                    'data': {},
                    'response_time': 0,
                    'last_check': 0
                }

    return health_data

def format_uptime(seconds):
    if seconds <= 0:
        return "Unknown"

    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60

    if days > 0:
        return f"{days}d {hours}h {minutes}m"
    elif hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m"

def format_time_ago(timestamp):
    if timestamp == 0:
        return "Never"

    delta = int(time.time()) - timestamp
    if delta < 60:
        return f"{delta}s ago"
    elif delta < 3600:
        return f"{delta // 60}m ago"
    elif delta < 86400:
        return f"{delta // 3600}h ago"
    else:
        return f"{delta // 86400}d ago"

@app.route('/')
def dashboard():
    health_data = get_latest_health()

    dashboard_html = '''
<!DOCTYPE html>
<html>
<head>
    <title>Rustchain Multi-Node Health Dashboard</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0f1419; color: #e6edf3; line-height: 1.6;
        }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        .header {
            text-align: center; margin-bottom: 30px;
            border-bottom: 2px solid #30363d; padding-bottom: 20px;
        }
        .header h1 { color: #58a6ff; font-size: 2.5rem; margin-bottom: 10px; }
        .header p { color: #8b949e; font-size: 1.1rem; }

        .nodes-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px; margin-bottom: 30px;
        }

        .node-card {
            background: #161b22; border: 1px solid #30363d;
            border-radius: 12px; padding: 24px; position: relative;
            transition: all 0.3s ease;
        }
        .node-card:hover { border-color: #58a6ff; transform: translateY(-2px); }

        .status-indicator {
            position: absolute; top: 20px; right: 20px;
            width: 16px; height: 16px; border-radius: 50%;
            display: flex; align-items: center; justify-content: center;
        }
        .status-up { background: #238636; }
        .status-down { background: #da3633; }
        .status-degraded { background: #d29922; }
        .status-unknown { background: #656d76; }

        .node-header { margin-bottom: 20px; }
        .node-name { font-size: 1.4rem; font-weight: 600; color: #f0f6fc; }
        .node-role { color: #58a6ff; font-size: 0.9rem; margin-top: 4px; }

        .metrics-grid {
            display: grid; grid-template-columns: 1fr 1fr; gap: 16px;
        }
        .metric {
            background: #0d1117; padding: 12px; border-radius: 6px;
            border: 1px solid #21262d;
        }
        .metric-label { color: #8b949e; font-size: 0.85rem; margin-bottom: 4px; }
        .metric-value { color: #f0f6fc; font-weight: 500; }

        .full-width { grid-column: 1 / -1; }

        .footer {
            text-align: center; color: #656d76; font-size: 0.9rem;
            padding: 20px 0; border-top: 1px solid #30363d;
        }
        .refresh-info { color: #58a6ff; }

        @media (max-width: 768px) {
            .container { padding: 15px; }
            .header h1 { font-size: 2rem; }
            .nodes-grid { grid-template-columns: 1fr; }
            .metrics-grid { grid-template-columns: 1fr; }
        }

        .error-message {
            background: #da3633; color: white; padding: 8px 12px;
            border-radius: 6px; font-size: 0.85rem; margin-top: 8px;
        }
    </style>
    <script>
        setTimeout(function() { location.reload(); }, 30000);
    </script>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔗 Rustchain Multi-Node Dashboard</h1>
            <p>Real-time monitoring of all attestation nodes</p>
        </div>

        <div class="nodes-grid">
            {% for node_id, config in nodes.items() %}
            {% set health = health_data.get(node_id, {}) %}
            {% set data = health.get('data', {}) %}
            <div class="node-card">
                <div class="status-indicator status-{{ health.get('status', 'unknown') }}"></div>

                <div class="node-header">
                    <div class="node-name">{{ config.name }}</div>
                    <div class="node-role">{{ config.role }}</div>
                </div>

                <div class="metrics-grid">
                    <div class="metric">
                        <div class="metric-label">Status</div>
                        <div class="metric-value">
                            {% if health.get('status') == 'up' %}🟢 Online
                            {% elif health.get('status') == 'degraded' %}🟡 Degraded
                            {% elif health.get('status') == 'down' %}🔴 Offline
                            {% else %}⚫ Unknown{% endif %}
                        </div>
                    </div>

                    <div class="metric">
                        <div class="metric-label">Response Time</div>
                        <div class="metric-value">{{ "%.0f"|format(health.get('response_time', 0) * 1000) }}ms</div>
                    </div>

                    <div class="metric">
                        <div class="metric-label">Version</div>
                        <div class="metric-value">{{ data.get('version', 'Unknown') }}</div>
                    </div>

                    <div class="metric">
                        <div class="metric-label">Uptime</div>
                        <div class="metric-value">{{ format_uptime(data.get('uptime', 0)) }}</div>
                    </div>

                    <div class="metric">
                        <div class="metric-label">Database</div>
                        <div class="metric-value">{{ data.get('database_status', 'Unknown') }}</div>
                    </div>

                    <div class="metric">
                        <div class="metric-label">Backup Age</div>
                        <div class="metric-value">{{ format_time_ago(data.get('last_backup', 0)) }}</div>
                    </div>

                    <div class="metric">
                        <div class="metric-label">Tip Age</div>
                        <div class="metric-value">{{ format_time_ago(data.get('tip_timestamp', 0)) }}</div>
                    </div>

                    <div class="metric">
                        <div class="metric-label">Miners</div>
                        <div class="metric-value">{{ data.get('active_miners', 0) }}</div>
                    </div>

                    <div class="metric">
                        <div class="metric-label">Current Epoch</div>
                        <div class="metric-value">{{ data.get('current_epoch', 'N/A') }}</div>
                    </div>

                    <div class="metric">
                        <div class="metric-label">Last Check</div>
                        <div class="metric-value">{{ format_time_ago(health.get('last_check', 0)) }}</div>
                    </div>

                    {% if data.get('error') %}
                    <div class="metric full-width">
                        <div class="error-message">{{ data.error }}</div>
                    </div>
                    {% endif %}
                </div>
            </div>
            {% endfor %}
        </div>

        <div class="footer">
            <div class="refresh-info">Auto-refreshes every 30 seconds</div>
            <div>Last updated: {{ current_time }}</div>
        </div>
    </div>
</body>
</html>
    '''

    return render_template_string(
        dashboard_html,
        nodes=NODES,
        health_data=health_data,
        format_uptime=format_uptime,
        format_time_ago=format_time_ago,
        current_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    )

@app.route('/api/health')
def api_health():
    health_data = get_latest_health()
    return {
        'nodes': health_data,
        'timestamp': int(time.time())
    }

if __name__ == '__main__':
    init_db()

    # Start background health monitor
    monitor_thread = threading.Thread(target=health_monitor, daemon=True)
    monitor_thread.start()

    # Initial health check
    for node_id, config in NODES.items():
        fetch_node_health(node_id, config)

    app.run(host='0.0.0.0', port=8088, debug=False)
