# SPDX-License-Identifier: MIT

from flask import Flask, render_template_string, jsonify, request
import sqlite3
import json
import time
import requests
from datetime import datetime, timedelta
from threading import Thread
import logging
import os

DB_PATH = 'multi_node_health.db'

app = Flask(__name__)
app.secret_key = os.urandom(24)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration for the 3 attestation nodes
NODE_CONFIG = {
    'node1': {
        'name': 'Attestation Node Alpha',
        'host': '127.0.0.1',
        'port': 8000,
        'endpoint': '/health'
    },
    'node2': {
        'name': 'Attestation Node Beta',
        'host': '127.0.0.1',
        'port': 8001,
        'endpoint': '/health'
    },
    'node3': {
        'name': 'Attestation Node Gamma',
        'host': '127.0.0.1',
        'port': 8002,
        'endpoint': '/health'
    }
}

def init_database():
    """Initialize the database with required tables"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS node_health (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id TEXT NOT NULL,
                status TEXT NOT NULL,
                response_time REAL,
                cpu_usage REAL,
                memory_usage REAL,
                disk_usage REAL,
                uptime INTEGER,
                last_block INTEGER,
                peer_count INTEGER,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        conn.execute('''
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id TEXT NOT NULL,
                alert_type TEXT NOT NULL,
                message TEXT NOT NULL,
                severity TEXT NOT NULL,
                resolved BOOLEAN DEFAULT FALSE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                resolved_at DATETIME
            )
        ''')

        conn.commit()

def check_node_health(node_id, config):
    """Check health of a single node"""
    try:
        start_time = time.time()
        url = f"http://{config['host']}:{config['port']}{config['endpoint']}"

        response = requests.get(url, timeout=5)
        response_time = (time.time() - start_time) * 1000

        if response.status_code == 200:
            data = response.json()

            health_data = {
                'node_id': node_id,
                'status': 'healthy',
                'response_time': response_time,
                'cpu_usage': data.get('cpu_usage', 0.0),
                'memory_usage': data.get('memory_usage', 0.0),
                'disk_usage': data.get('disk_usage', 0.0),
                'uptime': data.get('uptime', 0),
                'last_block': data.get('last_block', 0),
                'peer_count': data.get('peer_count', 0)
            }
        else:
            health_data = {
                'node_id': node_id,
                'status': 'unhealthy',
                'response_time': response_time,
                'cpu_usage': None,
                'memory_usage': None,
                'disk_usage': None,
                'uptime': None,
                'last_block': None,
                'peer_count': None
            }

    except Exception as e:
        logger.error(f"Health check failed for {node_id}: {str(e)}")
        health_data = {
            'node_id': node_id,
            'status': 'offline',
            'response_time': None,
            'cpu_usage': None,
            'memory_usage': None,
            'disk_usage': None,
            'uptime': None,
            'last_block': None,
            'peer_count': None
        }

    # Store health data
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            INSERT INTO node_health (
                node_id, status, response_time, cpu_usage, memory_usage,
                disk_usage, uptime, last_block, peer_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            health_data['node_id'], health_data['status'], health_data['response_time'],
            health_data['cpu_usage'], health_data['memory_usage'], health_data['disk_usage'],
            health_data['uptime'], health_data['last_block'], health_data['peer_count']
        ))
        conn.commit()

    # Check for alert conditions
    check_alerts(node_id, health_data)

    return health_data

def check_alerts(node_id, health_data):
    """Check for alert conditions and store alerts"""
    alerts = []

    if health_data['status'] == 'offline':
        alerts.append({
            'type': 'node_offline',
            'message': f'Node {node_id} is offline',
            'severity': 'critical'
        })
    elif health_data['status'] == 'unhealthy':
        alerts.append({
            'type': 'node_unhealthy',
            'message': f'Node {node_id} returned unhealthy status',
            'severity': 'warning'
        })

    if health_data['cpu_usage'] and health_data['cpu_usage'] > 90:
        alerts.append({
            'type': 'high_cpu',
            'message': f'Node {node_id} CPU usage is {health_data["cpu_usage"]:.1f}%',
            'severity': 'warning'
        })

    if health_data['memory_usage'] and health_data['memory_usage'] > 85:
        alerts.append({
            'type': 'high_memory',
            'message': f'Node {node_id} memory usage is {health_data["memory_usage"]:.1f}%',
            'severity': 'warning'
        })

    if health_data['response_time'] and health_data['response_time'] > 2000:
        alerts.append({
            'type': 'slow_response',
            'message': f'Node {node_id} slow response time: {health_data["response_time"]:.0f}ms',
            'severity': 'warning'
        })

    # Store alerts in database
    with sqlite3.connect(DB_PATH) as conn:
        for alert in alerts:
            conn.execute('''
                INSERT INTO alerts (node_id, alert_type, message, severity)
                VALUES (?, ?, ?, ?)
            ''', (node_id, alert['type'], alert['message'], alert['severity']))
        conn.commit()

def health_check_worker():
    """Background worker to continuously check node health"""
    while True:
        for node_id, config in NODE_CONFIG.items():
            check_node_health(node_id, config)
        time.sleep(30)  # Check every 30 seconds

@app.route('/')
def dashboard():
    """Main dashboard view"""
    html_template = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Multi-Node Health Dashboard</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }
            .header { background: #2c3e50; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
            .node-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 20px; }
            .node-card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            .status-healthy { border-left: 5px solid #27ae60; }
            .status-unhealthy { border-left: 5px solid #f39c12; }
            .status-offline { border-left: 5px solid #e74c3c; }
            .metric { display: flex; justify-content: space-between; margin: 10px 0; padding: 8px; background: #f8f9fa; border-radius: 4px; }
            .alerts-section { margin-top: 30px; background: white; padding: 20px; border-radius: 8px; }
            .alert { padding: 10px; margin: 5px 0; border-radius: 4px; }
            .alert-critical { background: #ffebee; border-left: 4px solid #e74c3c; }
            .alert-warning { background: #fff3e0; border-left: 4px solid #f39c12; }
            .refresh-btn { background: #3498db; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; }
            .refresh-btn:hover { background: #2980b9; }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🔗 Multi-Node Health Dashboard</h1>
            <p>Real-time monitoring of 3 Rustchain attestation nodes</p>
            <button class="refresh-btn" onclick="location.reload()">Refresh Data</button>
        </div>

        <div class="node-grid" id="nodeGrid">
            <!-- Nodes will be loaded here -->
        </div>

        <div class="alerts-section">
            <h2>🚨 Active Alerts</h2>
            <div id="alertsList">
                <!-- Alerts will be loaded here -->
            </div>
        </div>

        <script>
            function loadDashboard() {
                fetch('/api/nodes')
                    .then(response => response.json())
                    .then(data => {
                        const grid = document.getElementById('nodeGrid');
                        grid.innerHTML = '';

                        data.nodes.forEach(node => {
                            const card = createNodeCard(node);
                            grid.appendChild(card);
                        });
                    })
                    .catch(error => console.error('Error loading nodes:', error));

                fetch('/api/alerts')
                    .then(response => response.json())
                    .then(data => {
                        const alertsList = document.getElementById('alertsList');
                        alertsList.innerHTML = '';

                        if (data.alerts.length === 0) {
                            alertsList.innerHTML = '<p>No active alerts</p>';
                        } else {
                            data.alerts.forEach(alert => {
                                const alertDiv = createAlertDiv(alert);
                                alertsList.appendChild(alertDiv);
                            });
                        }
                    })
                    .catch(error => console.error('Error loading alerts:', error));
            }

            function createNodeCard(node) {
                const card = document.createElement('div');
                card.className = `node-card status-${node.status}`;

                const statusIcon = node.status === 'healthy' ? '✅' :
                                 node.status === 'unhealthy' ? '⚠️' : '❌';

                card.innerHTML = `
                    <h3>${statusIcon} ${node.name}</h3>
                    <div class="metric">
                        <span>Status:</span>
                        <span><strong>${node.status.toUpperCase()}</strong></span>
                    </div>
                    <div class="metric">
                        <span>Response Time:</span>
                        <span>${node.response_time ? node.response_time.toFixed(0) + 'ms' : 'N/A'}</span>
                    </div>
                    <div class="metric">
                        <span>CPU Usage:</span>
                        <span>${node.cpu_usage ? node.cpu_usage.toFixed(1) + '%' : 'N/A'}</span>
                    </div>
                    <div class="metric">
                        <span>Memory Usage:</span>
                        <span>${node.memory_usage ? node.memory_usage.toFixed(1) + '%' : 'N/A'}</span>
                    </div>
                    <div class="metric">
                        <span>Peer Count:</span>
                        <span>${node.peer_count !== null ? node.peer_count : 'N/A'}</span>
                    </div>
                    <div class="metric">
                        <span>Last Block:</span>
                        <span>${node.last_block !== null ? node.last_block : 'N/A'}</span>
                    </div>
                    <div class="metric">
                        <span>Last Check:</span>
                        <span>${new Date(node.timestamp).toLocaleTimeString()}</span>
                    </div>
                `;

                return card;
            }

            function createAlertDiv(alert) {
                const div = document.createElement('div');
                div.className = `alert alert-${alert.severity}`;
                div.innerHTML = `
                    <strong>${alert.node_id.toUpperCase()}:</strong> ${alert.message}
                    <small style="float: right;">${new Date(alert.created_at).toLocaleString()}</small>
                `;
                return div;
            }

            // Load dashboard on page load
            loadDashboard();

            // Auto-refresh every 30 seconds
            setInterval(loadDashboard, 30000);
        </script>
    </body>
    </html>
    '''
    return render_template_string(html_template)

@app.route('/api/nodes')
def api_nodes():
    """API endpoint to get current node status"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        nodes = []
        for node_id, config in NODE_CONFIG.items():
            # Get latest health data for each node
            cursor.execute('''
                SELECT * FROM node_health
                WHERE node_id = ?
                ORDER BY timestamp DESC
                LIMIT 1
            ''', (node_id,))

            row = cursor.fetchone()
            if row:
                node_data = {
                    'node_id': row[1],
                    'name': config['name'],
                    'status': row[2],
                    'response_time': row[3],
                    'cpu_usage': row[4],
                    'memory_usage': row[5],
                    'disk_usage': row[6],
                    'uptime': row[7],
                    'last_block': row[8],
                    'peer_count': row[9],
                    'timestamp': row[10]
                }
            else:
                node_data = {
                    'node_id': node_id,
                    'name': config['name'],
                    'status': 'unknown',
                    'response_time': None,
                    'cpu_usage': None,
                    'memory_usage': None,
                    'disk_usage': None,
                    'uptime': None,
                    'last_block': None,
                    'peer_count': None,
                    'timestamp': None
                }

            nodes.append(node_data)

    return jsonify({'nodes': nodes})

@app.route('/api/alerts')
def api_alerts():
    """API endpoint to get active alerts"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT node_id, alert_type, message, severity, created_at
            FROM alerts
            WHERE resolved = FALSE
            ORDER BY created_at DESC
            LIMIT 50
        ''')

        alerts = []
        for row in cursor.fetchall():
            alerts.append({
                'node_id': row[0],
                'alert_type': row[1],
                'message': row[2],
                'severity': row[3],
                'created_at': row[4]
            })

    return jsonify({'alerts': alerts})

@app.route('/api/metrics/<node_id>')
def api_node_metrics(node_id):
    """API endpoint to get historical metrics for a specific node"""
    hours = request.args.get('hours', 24, type=int)

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT timestamp, cpu_usage, memory_usage, response_time
            FROM node_health
            WHERE node_id = ? AND timestamp > datetime('now', '-{} hours')
            ORDER BY timestamp ASC
        '''.format(hours), (node_id,))

        metrics = []
        for row in cursor.fetchall():
            metrics.append({
                'timestamp': row[0],
                'cpu_usage': row[1],
                'memory_usage': row[2],
                'response_time': row[3]
            })

    return jsonify({'metrics': metrics})

if __name__ == '__main__':
    init_database()

    # Start background health check worker
    health_thread = Thread(target=health_check_worker, daemon=True)
    health_thread.start()

    logger.info("Starting Multi-Node Health Dashboard")
    app.run(host='0.0.0.0', port=5000, debug=False)
