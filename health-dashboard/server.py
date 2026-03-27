#!/usr/bin/env python3
"""
RustChain Multi-Node Health Dashboard - Backend Server
Monitors all RustChain attestation nodes and provides a live status page.

Bounty Issue #2300
"""
import asyncio
import json
import logging
import os
import sqlite3
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse
import threading
import requests
from flask import Flask, jsonify, render_template_string, send_from_directory

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('health-dashboard')

# Configuration
BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / 'static'
TEMPLATES_DIR = BASE_DIR / 'templates'
DATA_DIR = BASE_DIR / 'data'
DATA_DIR.mkdir(exist_ok=True)

DB_PATH = DATA_DIR / 'health_history.db'
POLLING_INTERVAL = int(os.environ.get('POLLING_INTERVAL', 60))  # 60 seconds
HISTORY_RETENTION_HOURS = 24

# Node configuration from issue #2300
NODES = [
    {
        'id': 'node1',
        'name': 'Node 1 - LiquidWeb US #1',
        'endpoint': 'https://50.28.86.131/health',
        'location': 'LiquidWeb US',
        'lat': 42.3314,
        'lng': -83.0458
    },
    {
        'id': 'node2',
        'name': 'Node 2 - LiquidWeb US #2',
        'endpoint': 'https://50.28.86.153/health',
        'location': 'LiquidWeb US',
        'lat': 42.3314,
        'lng': -83.0458
    },
    {
        'id': 'node3',
        'name': 'Node 3 - Ryan\'s Proxmox',
        'endpoint': 'http://76.8.228.245:8099/health',
        'location': 'Ryan\'s Proxmox',
        'lat': 40.7128,
        'lng': -74.0060
    },
    {
        'id': 'node4',
        'name': 'Node 4 - Hong Kong',
        'endpoint': 'http://38.76.217.189:8099/health',
        'location': 'Hong Kong',
        'lat': 22.3193,
        'lng': 114.1694
    }
]

# Webhook configuration (bonus feature)
DISCORD_WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK_URL', '')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')

# In-memory state
current_status: Dict[str, dict] = {}
incident_log: List[dict] = []


@dataclass
class NodeStatus:
    """Represents the current status of a node"""
    node_id: str
    name: str
    endpoint: str
    location: str
    status: str  # 'up', 'down', 'degraded'
    response_time_ms: float
    version: str
    uptime_s: int
    active_miners: int
    current_epoch: int
    timestamp: datetime
    error: Optional[str] = None


def init_database():
    """Initialize SQLite database for historical data"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create tables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS health_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            node_id TEXT NOT NULL,
            timestamp DATETIME NOT NULL,
            status TEXT NOT NULL,
            response_time_ms REAL,
            version TEXT,
            uptime_s INTEGER,
            active_miners INTEGER,
            current_epoch INTEGER
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            node_id TEXT NOT NULL,
            incident_type TEXT NOT NULL,
            timestamp DATETIME NOT NULL,
            details TEXT,
            resolved_at DATETIME,
            duration_seconds INTEGER
        )
    ''')
    
    # Create indexes for performance
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_health_node_time 
        ON health_history(node_id, timestamp)
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_incidents_node_time 
        ON incidents(node_id, timestamp)
    ''')
    
    conn.commit()
    conn.close()
    logger.info(f"Database initialized at {DB_PATH}")


def record_health(status: NodeStatus):
    """Record health status to database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO health_history 
        (node_id, timestamp, status, response_time_ms, version, uptime_s, active_miners, current_epoch)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        status.node_id,
        status.timestamp.isoformat(),
        status.status,
        status.response_time_ms,
        status.version,
        status.uptime_s,
        status.active_miners,
        status.current_epoch
    ))
    
    conn.commit()
    conn.close()


def record_incident(node_id: str, incident_type: str, details: str):
    """Record an incident to the database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO incidents (node_id, incident_type, timestamp, details)
        VALUES (?, ?, ?, ?)
    ''', (node_id, incident_type, datetime.now().isoformat(), details))
    
    conn.commit()
    conn.close()
    
    # Add to in-memory log
    incident_log.append({
        'node_id': node_id,
        'incident_type': incident_type,
        'timestamp': datetime.now().isoformat(),
        'details': details
    })


def cleanup_old_data():
    """Remove data older than HISTORY_RETENTION_HOURS"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cutoff = (datetime.now() - timedelta(hours=HISTORY_RETENTION_HOURS)).isoformat()
    
    cursor.execute('DELETE FROM health_history WHERE timestamp < ?', (cutoff,))
    cursor.execute('DELETE FROM incidents WHERE timestamp < ?', (cutoff,))
    
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    
    if deleted > 0:
        logger.info(f"Cleaned up {deleted} old records")


def check_node_health(node_config: dict) -> NodeStatus:
    """Check health of a single node"""
    start_time = time.time()
    timestamp = datetime.now()
    
    try:
        # Use pinned cert for HTTPS, no verification needed for plain HTTP
        _cert = os.path.expanduser("~/.rustchain/node_cert.pem")
        if 'https://' in node_config['endpoint']:
            verify = _cert if os.path.exists(_cert) else True
        else:
            verify = False  # Plain HTTP has no TLS to verify
        
        response = requests.get(
            node_config['endpoint'],
            timeout=10,
            verify=verify
        )
        response_time_ms = (time.time() - start_time) * 1000
        
        if response.status_code == 200:
            data = response.json()
            return NodeStatus(
                node_id=node_config['id'],
                name=node_config['name'],
                endpoint=node_config['endpoint'],
                location=node_config['location'],
                status='up',
                response_time_ms=response_time_ms,
                version=data.get('version', 'unknown'),
                uptime_s=data.get('uptime_s', 0),
                active_miners=data.get('active_miners', 0),
                current_epoch=data.get('epoch', 0),
                timestamp=timestamp
            )
        else:
            return NodeStatus(
                node_id=node_config['id'],
                name=node_config['name'],
                endpoint=node_config['endpoint'],
                location=node_config['location'],
                status='down',
                response_time_ms=response_time_ms,
                version='unknown',
                uptime_s=0,
                active_miners=0,
                current_epoch=0,
                timestamp=timestamp,
                error=f"HTTP {response.status_code}"
            )
            
    except requests.exceptions.Timeout:
        return NodeStatus(
            node_id=node_config['id'],
            name=node_config['name'],
            endpoint=node_config['endpoint'],
            location=node_config['location'],
            status='down',
            response_time_ms=(time.time() - start_time) * 1000,
            version='unknown',
            uptime_s=0,
            active_miners=0,
            current_epoch=0,
            timestamp=timestamp,
            error="Timeout"
        )
    except requests.exceptions.ConnectionError as e:
        return NodeStatus(
            node_id=node_config['id'],
            name=node_config['name'],
            endpoint=node_config['endpoint'],
            location=node_config['location'],
            status='down',
            response_time_ms=(time.time() - start_time) * 1000,
            version='unknown',
            uptime_s=0,
            active_miners=0,
            current_epoch=0,
            timestamp=timestamp,
            error="Connection Error"
        )
    except Exception as e:
        return NodeStatus(
            node_id=node_config['id'],
            name=node_config['name'],
            endpoint=node_config['endpoint'],
            location=node_config['location'],
            status='down',
            response_time_ms=(time.time() - start_time) * 1000,
            version='unknown',
            uptime_s=0,
            active_miners=0,
            current_epoch=0,
            timestamp=timestamp,
            error=str(e)
        )


def detect_status_change(old_status: dict, new_status: NodeStatus):
    """Detect and log status changes (incidents)"""
    if old_status is None:
        return
    
    old = old_status.get('status')
    new = new_status.status
    
    if old != new:
        if new == 'down':
            incident_type = 'node_down'
            details = f"Node {new_status.name} went DOWN. Error: {new_status.error or 'Unknown'}"
            logger.warning(f"INCIDENT: {details}")
        elif old == 'down' and new == 'up':
            incident_type = 'node_recovery'
            details = f"Node {new_status.name} recovered and is back UP"
            logger.info(f"INCIDENT: {details}")
        else:
            return
        
        record_incident(new_status.node_id, incident_type, details)
        
        # Send webhook notifications (bonus feature)
        send_webhook_notification(incident_type, new_status)


def send_webhook_notification(incident_type: str, status: NodeStatus):
    """Send notifications to Discord/Telegram (bonus feature)"""
    if incident_type == 'node_down' and DISCORD_WEBHOOK_URL:
        try:
            payload = {
                'embeds': [{
                    'title': '🚨 Node Down Alert',
                    'description': f"Node **{status.name}** is DOWN",
                    'color': 16711680,  # Red
                    'fields': [
                        {'name': 'Endpoint', 'value': status.endpoint, 'inline': False},
                        {'name': 'Error', 'value': status.error or 'Unknown', 'inline': False},
                        {'name': 'Location', 'value': status.location, 'inline': True}
                    ],
                    'timestamp': datetime.now().isoformat()
                }]
            }
            requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=5)
            logger.info("Discord notification sent")
        except Exception as e:
            logger.error(f"Failed to send Discord notification: {e}")
    
    if incident_type == 'node_down' and TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        try:
            message = (
                f"🚨 *Node Down Alert*\n\n"
                f"*Node:* {status.name}\n"
                f"*Endpoint:* `{status.endpoint}`\n"
                f"*Error:* {status.error or 'Unknown'}\n"
                f"*Location:* {status.location}"
            )
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            requests.post(url, json={
                'chat_id': TELEGRAM_CHAT_ID,
                'text': message,
                'parse_mode': 'Markdown'
            }, timeout=5)
            logger.info("Telegram notification sent")
        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {e}")


def poll_nodes():
    """Poll all nodes and update status"""
    logger.info("Polling nodes...")
    
    for node_config in NODES:
        old_status = current_status.get(node_config['id'])
        new_status = check_node_health(node_config)
        
        # Update in-memory status
        current_status[node_config['id']] = {
            'node_id': new_status.node_id,
            'name': new_status.name,
            'endpoint': new_status.endpoint,
            'location': new_status.location,
            'status': new_status.status,
            'response_time_ms': round(new_status.response_time_ms, 2),
            'version': new_status.version,
            'uptime_s': new_status.uptime_s,
            'active_miners': new_status.active_miners,
            'current_epoch': new_status.current_epoch,
            'timestamp': new_status.timestamp.isoformat(),
            'error': new_status.error,
            'lat': node_config['lat'],
            'lng': node_config['lng']
        }
        
        # Record to database
        record_health(new_status)
        
        # Detect and log incidents
        detect_status_change(old_status, new_status)
    
    # Cleanup old data periodically
    cleanup_old_data()
    
    logger.info(f"Poll complete. Status: {sum(1 for s in current_status.values() if s['status'] == 'up')}/{len(NODES)} nodes up")


def poll_loop():
    """Background polling loop"""
    while True:
        try:
            poll_nodes()
        except Exception as e:
            logger.error(f"Error in poll loop: {e}")
        time.sleep(POLLING_INTERVAL)


# Flask application
app = Flask(__name__, 
            static_folder=str(STATIC_DIR),
            template_folder=str(TEMPLATES_DIR))


@app.route('/')
def dashboard():
    """Serve the main dashboard page"""
    return render_template_string(HTML_TEMPLATE)


@app.route('/api/status')
def api_status():
    """API endpoint for current node status"""
    return jsonify({
        'nodes': list(current_status.values()),
        'last_updated': datetime.now().isoformat(),
        'total_nodes': len(NODES),
        'nodes_up': sum(1 for s in current_status.values() if s['status'] == 'up'),
        'nodes_down': sum(1 for s in current_status.values() if s['status'] == 'down')
    })


@app.route('/api/history/<node_id>')
def api_history(node_id: str):
    """API endpoint for historical data (24 hours)"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cutoff = (datetime.now() - timedelta(hours=HISTORY_RETENTION_HOURS)).isoformat()
    
    cursor.execute('''
        SELECT timestamp, status, response_time_ms, uptime_s, active_miners, current_epoch
        FROM health_history
        WHERE node_id = ? AND timestamp >= ?
        ORDER BY timestamp ASC
    ''', (node_id, cutoff))
    
    rows = cursor.fetchall()
    conn.close()
    
    return jsonify({
        'node_id': node_id,
        'history': [dict(row) for row in rows]
    })


@app.route('/api/incidents')
def api_incidents():
    """API endpoint for incident log"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cutoff = (datetime.now() - timedelta(hours=HISTORY_RETENTION_HOURS)).isoformat()
    
    cursor.execute('''
        SELECT id, node_id, incident_type, timestamp, details, resolved_at, duration_seconds
        FROM incidents
        WHERE timestamp >= ?
        ORDER BY timestamp DESC
        LIMIT 100
    ''', (cutoff,))
    
    rows = cursor.fetchall()
    conn.close()
    
    return jsonify({
        'incidents': [dict(row) for row in rows]
    })


@app.route('/feed/incidents.xml')
def rss_feed():
    """RSS/Atom feed for incidents (bonus feature)"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cutoff = (datetime.now() - timedelta(days=7)).isoformat()
    
    cursor.execute('''
        SELECT id, node_id, incident_type, timestamp, details
        FROM incidents
        WHERE timestamp >= ?
        ORDER BY timestamp DESC
        LIMIT 50
    ''', (cutoff,))
    
    rows = cursor.fetchall()
    conn.close()
    
    # Generate Atom feed
    feed_items = []
    for row in rows:
        node_name = next((n['name'] for n in NODES if n['id'] == row['node_id']), row['node_id'])
        feed_items.append(f'''
    <entry>
        <title>{row['incident_type'].replace('_', ' ').title()}: {node_name}</title>
        <link href="https://rustchain.org/status"/>
        <id>tag:rustchain.org,2026:incident-{row['id']}</id>
        <published>{row['timestamp']}</published>
        <updated>{row['timestamp']}</updated>
        <content type="html">{row['details']}</content>
    </entry>''')
    
    feed_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
    <title>RustChain Node Incidents</title>
    <subtitle>Incident feed for RustChain attestation nodes</subtitle>
    <link href="https://rustchain.org/status/feed/incidents.xml" rel="self"/>
    <link href="https://rustchain.org/status"/>
    <updated>{datetime.now().isoformat()}</updated>
    <id>tag:rustchain.org,2026:incidents</id>
    {''.join(feed_items)}
</feed>'''
    
    return feed_xml, 200, {'Content-Type': 'application/atom+xml'}


@app.route('/static/<path:path>')
def serve_static(path):
    """Serve static files"""
    return send_from_directory(STATIC_DIR, path)


# HTML Template (inline for single-file deployment)
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RustChain Network Status</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {
            --bg-primary: #0f172a;
            --bg-secondary: #1e293b;
            --bg-card: #334155;
            --text-primary: #f1f5f9;
            --text-secondary: #94a3b8;
            --success: #22c55e;
            --danger: #ef4444;
            --warning: #f59e0b;
            --border: #475569;
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        
        header {
            text-align: center;
            margin-bottom: 30px;
            padding: 20px;
            background: var(--bg-secondary);
            border-radius: 12px;
            border: 1px solid var(--border);
        }
        
        h1 {
            font-size: 2rem;
            margin-bottom: 10px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        
        .subtitle {
            color: var(--text-secondary);
            font-size: 0.9rem;
        }
        
        .status-summary {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 30px;
        }
        
        .summary-card {
            background: var(--bg-secondary);
            padding: 20px;
            border-radius: 10px;
            text-align: center;
            border: 1px solid var(--border);
        }
        
        .summary-card h3 {
            color: var(--text-secondary);
            font-size: 0.85rem;
            margin-bottom: 10px;
        }
        
        .summary-card .value {
            font-size: 2rem;
            font-weight: bold;
        }
        
        .summary-card .value.up { color: var(--success); }
        .summary-card .value.down { color: var(--danger); }
        
        .nodes-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .node-card {
            background: var(--bg-card);
            border-radius: 12px;
            padding: 20px;
            border: 1px solid var(--border);
            transition: transform 0.2s;
        }
        
        .node-card:hover {
            transform: translateY(-2px);
        }
        
        .node-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }
        
        .node-name {
            font-weight: bold;
            font-size: 1.1rem;
        }
        
        .status-badge {
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 0.8rem;
            font-weight: bold;
            text-transform: uppercase;
        }
        
        .status-badge.up {
            background: rgba(34, 197, 94, 0.2);
            color: var(--success);
        }
        
        .status-badge.down {
            background: rgba(239, 68, 68, 0.2);
            color: var(--danger);
        }
        
        .node-metrics {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 10px;
        }
        
        .metric {
            background: var(--bg-secondary);
            padding: 10px;
            border-radius: 8px;
        }
        
        .metric-label {
            font-size: 0.75rem;
            color: var(--text-secondary);
            margin-bottom: 5px;
        }
        
        .metric-value {
            font-size: 1.1rem;
            font-weight: bold;
        }
        
        .charts-section {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(500px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .chart-card {
            background: var(--bg-card);
            border-radius: 12px;
            padding: 20px;
            border: 1px solid var(--border);
        }
        
        .chart-card h3 {
            margin-bottom: 15px;
            color: var(--text-secondary);
            font-size: 1rem;
        }
        
        .incident-log {
            background: var(--bg-card);
            border-radius: 12px;
            padding: 20px;
            border: 1px solid var(--border);
            margin-bottom: 30px;
        }
        
        .incident-log h3 {
            margin-bottom: 15px;
            color: var(--text-secondary);
        }
        
        .incident-item {
            padding: 12px;
            background: var(--bg-secondary);
            border-radius: 8px;
            margin-bottom: 10px;
            border-left: 4px solid var(--danger);
        }
        
        .incident-item.recovery {
            border-left-color: var(--success);
        }
        
        .incident-time {
            font-size: 0.8rem;
            color: var(--text-secondary);
            margin-bottom: 5px;
        }
        
        .incident-details {
            font-size: 0.95rem;
        }
        
        .map-section {
            background: var(--bg-card);
            border-radius: 12px;
            padding: 20px;
            border: 1px solid var(--border);
            margin-bottom: 30px;
        }
        
        .map-section h3 {
            margin-bottom: 15px;
            color: var(--text-secondary);
        }
        
        #map {
            width: 100%;
            height: 400px;
            border-radius: 8px;
            background: var(--bg-secondary);
        }
        
        .last-updated {
            text-align: center;
            color: var(--text-secondary);
            font-size: 0.85rem;
            margin-top: 20px;
        }
        
        .error-text {
            color: var(--danger);
            font-size: 0.85rem;
            margin-top: 5px;
        }
        
        @media (max-width: 768px) {
            .charts-section {
                grid-template-columns: 1fr;
            }
            
            .nodes-grid {
                grid-template-columns: 1fr;
            }
            
            h1 {
                font-size: 1.5rem;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🔗 RustChain Network Status</h1>
            <p class="subtitle">Real-time monitoring of RustChain attestation nodes</p>
        </header>
        
        <div class="status-summary">
            <div class="summary-card">
                <h3>Total Nodes</h3>
                <div class="value" id="total-nodes">4</div>
            </div>
            <div class="summary-card">
                <h3>Nodes Up</h3>
                <div class="value up" id="nodes-up">-</div>
            </div>
            <div class="summary-card">
                <h3>Nodes Down</h3>
                <div class="value down" id="nodes-down">-</div>
            </div>
            <div class="summary-card">
                <h3>Overall Status</h3>
                <div class="value" id="overall-status">-</div>
            </div>
        </div>
        
        <div class="nodes-grid" id="nodes-grid">
            <!-- Node cards will be inserted here -->
        </div>
        
        <div class="map-section">
            <h3>🌍 Node Locations</h3>
            <div id="map"></div>
        </div>
        
        <div class="charts-section">
            <div class="chart-card">
                <h3>📊 Response Time (24h)</h3>
                <canvas id="response-time-chart"></canvas>
            </div>
            <div class="chart-card">
                <h3>📈 Uptime Timeline (24h)</h3>
                <canvas id="uptime-chart"></canvas>
            </div>
        </div>
        
        <div class="incident-log">
            <h3>📋 Incident Log (24h)</h3>
            <div id="incident-list">
                <p style="color: var(--text-secondary);">Loading incidents...</p>
            </div>
        </div>
        
        <p class="last-updated">Last updated: <span id="last-updated">-</span></p>
    </div>
    
    <script>
        // State
        let responseTimeCharts = {};
        let uptimeChart = null;
        
        // Format timestamp
        function formatTime(isoString) {
            const date = new Date(isoString);
            return date.toLocaleString();
        }
        
        // Format duration
        function formatDuration(seconds) {
            if (seconds < 60) return `${seconds}s`;
            if (seconds < 3600) return `${Math.round(seconds/60)}m`;
            return `${Math.round(seconds/3600)}h`;
        }
        
        // Render node cards
        function renderNodes(nodes) {
            const grid = document.getElementById('nodes-grid');
            grid.innerHTML = nodes.map(node => `
                <div class="node-card">
                    <div class="node-header">
                        <span class="node-name">${node.name}</span>
                        <span class="status-badge ${node.status}">${node.status}</span>
                    </div>
                    <div class="node-metrics">
                        <div class="metric">
                            <div class="metric-label">Response Time</div>
                            <div class="metric-value">${node.status === 'up' ? node.response_time_ms.toFixed(0) + ' ms' : 'N/A'}</div>
                        </div>
                        <div class="metric">
                            <div class="metric-label">Version</div>
                            <div class="metric-value">${node.version}</div>
                        </div>
                        <div class="metric">
                            <div class="metric-label">Uptime</div>
                            <div class="metric-value">${formatDuration(node.uptime_s)}</div>
                        </div>
                        <div class="metric">
                            <div class="metric-label">Active Miners</div>
                            <div class="metric-value">${node.active_miners}</div>
                        </div>
                        <div class="metric">
                            <div class="metric-label">Current Epoch</div>
                            <div class="metric-value">#${node.current_epoch}</div>
                        </div>
                        <div class="metric">
                            <div class="metric-label">Location</div>
                            <div class="metric-value">${node.location}</div>
                        </div>
                    </div>
                    ${node.error ? `<div class="error-text">Error: ${node.error}</div>` : ''}
                </div>
            `).join('');
        }
        
        // Update summary
        function updateSummary(data) {
            document.getElementById('total-nodes').textContent = data.total_nodes;
            document.getElementById('nodes-up').textContent = data.nodes_up;
            document.getElementById('nodes-down').textContent = data.nodes_down;
            
            const overall = document.getElementById('overall-status');
            if (data.nodes_up === data.total_nodes) {
                overall.textContent = 'Healthy';
                overall.style.color = 'var(--success)';
            } else if (data.nodes_up > 0) {
                overall.textContent = 'Degraded';
                overall.style.color = 'var(--warning)';
            } else {
                overall.textContent = 'Critical';
                overall.style.color = 'var(--danger)';
            }
        }
        
        // Render incidents
        function renderIncidents(incidents) {
            const list = document.getElementById('incident-list');
            
            if (incidents.length === 0) {
                list.innerHTML = '<p style="color: var(--success);">No incidents in the last 24 hours ✓</p>';
                return;
            }
            
            list.innerHTML = incidents.map(incident => {
                const node = NODES.find(n => n.id === incident.node_id);
                const nodeName = node ? node.name : incident.node_id;
                const isRecovery = incident.incident_type === 'node_recovery';
                
                return `
                    <div class="incident-item ${isRecovery ? 'recovery' : ''}">
                        <div class="incident-time">${formatTime(incident.timestamp)}</div>
                        <div class="incident-details">
                            <strong>${isRecovery ? '✅' : '🚨'} ${incident.incident_type.replace('_', ' ').toUpperCase()}</strong><br>
                            ${nodeName}: ${incident.details}
                        </div>
                    </div>
                `;
            }).join('');
        }
        
        // Initialize charts
        function initCharts() {
            const ctx1 = document.getElementById('response-time-chart').getContext('2d');
            const ctx2 = document.getElementById('uptime-chart').getContext('2d');
            
            responseTimeCharts = {};
            NODES.forEach(node => {
                responseTimeCharts[node.id] = {
                    label: node.name,
                    data: [],
                    borderColor: getRandomColor(),
                    tension: 0.4
                };
            });
            
            new Chart(ctx1, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: Object.values(responseTimeCharts)
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: false,
                            grid: { color: 'rgba(255,255,255,0.1)' },
                            ticks: { color: '#94a3b8' }
                        },
                        x: {
                            grid: { color: 'rgba(255,255,255,0.1)' },
                            ticks: { color: '#94a3b8', maxTicksLimit: 8 }
                        }
                    },
                    plugins: {
                        legend: {
                            labels: { color: '#f1f5f9', font: { size: 10 } }
                        }
                    }
                }
            });
            
            uptimeChart = new Chart(ctx2, {
                type: 'bar',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'Uptime %',
                        data: [],
                        backgroundColor: 'rgba(34, 197, 94, 0.7)',
                        borderColor: 'rgba(34, 197, 94, 1)',
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: true,
                            max: 100,
                            grid: { color: 'rgba(255,255,255,0.1)' },
                            ticks: { 
                                color: '#94a3b8',
                                callback: value => value + '%'
                            }
                        },
                        x: {
                            grid: { color: 'rgba(255,255,255,0.1)' },
                            ticks: { color: '#94a3b8' }
                        }
                    },
                    plugins: {
                        legend: { display: false }
                    }
                }
            });
        }
        
        // Update charts with historical data
        async function updateCharts() {
            for (const node of NODES) {
                try {
                    const response = await fetch(`/api/history/${node.id}`);
                    const data = await response.json();
                    
                    if (data.history && data.history.length > 0) {
                        // Update response time chart
                        const chartData = responseTimeCharts[node.id];
                        chartData.data = data.history.map(h => h.response_time_ms || 0);
                        
                        // Calculate uptime percentage
                        const total = data.history.length;
                        const up = data.history.filter(h => h.status === 'up').length;
                        const uptimePercent = total > 0 ? (up / total * 100) : 100;
                        
                        if (uptimeChart) {
                            uptimeChart.data.labels.push(node.name.split(' - ')[0]);
                            uptimeChart.data.datasets[0].data.push(uptimePercent);
                            uptimeChart.data.datasets[0].backgroundColor.push(
                                uptimePercent === 100 
                                    ? 'rgba(34, 197, 94, 0.7)' 
                                    : 'rgba(239, 68, 68, 0.7)'
                            );
                        }
                    }
                } catch (error) {
                    console.error(`Error loading history for ${node.id}:`, error);
                }
            }
            
            if (uptimeChart) {
                uptimeChart.update();
            }
        }
        
        // Get random color for charts
        function getRandomColor() {
            const colors = ['#667eea', '#764ba2', '#f093fb', '#f5576c', '#4facfe', '#00f2fe'];
            return colors[Math.floor(Math.random() * colors.length)];
        }
        
        // Initialize map (simple SVG-based map)
        function initMap() {
            const mapDiv = document.getElementById('map');
            
            // Simple node location visualization
            const locations = NODES.map(node => `
                <div style="
                    position: absolute;
                    left: ${(node.lng + 180) / 360 * 100}%;
                    top: ${(90 - node.lat) / 180 * 100}%;
                    width: 12px;
                    height: 12px;
                    background: ${current_status[node.id]?.status === 'up' ? '#22c55e' : '#ef4444'};
                    border: 2px solid white;
                    border-radius: 50%;
                    cursor: pointer;
                    transition: transform 0.2s;
                " 
                title="${node.name}: ${current_status[node.id]?.status || 'unknown'}"
                onmouseover="this.style.transform='scale(1.5)'"
                onmouseout="this.style.transform='scale(1)'"
                ></div>
            `).join('');
            
            mapDiv.innerHTML = `
                <div style="
                    position: relative;
                    width: 100%;
                    height: 100%;
                    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
                    border-radius: 8px;
                    overflow: hidden;
                ">
                    <div style="
                        position: absolute;
                        top: 0;
                        left: 0;
                        right: 0;
                        bottom: 0;
                        background-image: 
                            linear-gradient(rgba(255,255,255,0.05) 1px, transparent 1px),
                            linear-gradient(90deg, rgba(255,255,255,0.05) 1px, transparent 1px);
                        background-size: 50px 50px;
                    "></div>
                    ${locations}
                    <div style="
                        position: absolute;
                        bottom: 10px;
                        right: 10px;
                        background: rgba(0,0,0,0.7);
                        padding: 8px 12px;
                        border-radius: 6px;
                        font-size: 0.8rem;
                    ">
                        <span style="color: #22c55e;">●</span> Online &nbsp;
                        <span style="color: #ef4444;">●</span> Offline
                    </div>
                </div>
            `;
        }
        
        // Node configuration
        const NODES = [
            { id: 'node1', name: 'Node 1 - LiquidWeb US #1', lat: 42.3314, lng: -83.0458 },
            { id: 'node2', name: 'Node 2 - LiquidWeb US #2', lat: 42.3314, lng: -83.0458 },
            { id: 'node3', name: 'Node 3 - Ryan\'s Proxmox', lat: 40.7128, lng: -74.0060 },
            { id: 'node4', name: 'Node 4 - Hong Kong', lat: 22.3193, lng: 114.1694 }
        ];
        
        // Main update function
        async function updateDashboard() {
            try {
                const response = await fetch('/api/status');
                const data = await response.json();
                
                updateSummary(data);
                renderNodes(data.nodes);
                document.getElementById('last-updated').textContent = formatTime(data.last_updated);
                
                // Update map
                initMap();
                
            } catch (error) {
                console.error('Error fetching status:', error);
            }
            
            try {
                const response = await fetch('/api/incidents');
                const data = await response.json();
                renderIncidents(data.incidents || []);
            } catch (error) {
                console.error('Error fetching incidents:', error);
            }
        }
        
        // Initialize
        document.addEventListener('DOMContentLoaded', () => {
            initCharts();
            updateDashboard();
            
            // Auto-refresh every 60 seconds
            setInterval(updateDashboard, 60000);
            
            // Update charts every 5 minutes
            setInterval(updateCharts, 300000);
        });
    </script>
</body>
</html>
'''


def main():
    """Main entry point"""
    logger.info("Starting RustChain Multi-Node Health Dashboard...")
    logger.info(f"Polling interval: {POLLING_INTERVAL}s")
    logger.info(f"History retention: {HISTORY_RETENTION_HOURS}h")
    logger.info(f"Monitoring {len(NODES)} nodes")
    
    # Initialize database
    init_database()
    
    # Start background polling thread
    poll_thread = threading.Thread(target=poll_loop, daemon=True)
    poll_thread.start()
    
    # Initial poll
    poll_nodes()
    
    # Start Flask server
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"Starting web server on port {port}")
    
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)


if __name__ == '__main__':
    main()
