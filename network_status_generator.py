# SPDX-License-Identifier: MIT

import json
import os
import sqlite3
import time
from datetime import datetime
import requests
from flask import render_template_string

# Default node endpoints
DEFAULT_NODES = [
    "https://50.28.86.131",
    "https://node2.rustchain.network",
    "https://node3.rustchain.network"
]

# Database path for caching
DB_PATH = "network_status.db"

# HTML template for the status page
STATUS_PAGE_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RustChain Network Status</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            color: #333;
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: rgba(255,255,255,0.95);
            border-radius: 12px;
            padding: 30px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.2);
        }
        .header {
            text-align: center;
            margin-bottom: 40px;
            border-bottom: 2px solid #e0e6ed;
            padding-bottom: 20px;
        }
        .header h1 {
            color: #1e3c72;
            font-size: 2.5em;
            margin-bottom: 10px;
        }
        .header p {
            color: #666;
            font-size: 1.1em;
            max-width: 600px;
            margin: 0 auto;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }
        .stat-card {
            background: white;
            border: 1px solid #e0e6ed;
            border-radius: 8px;
            padding: 20px;
            text-align: center;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        .stat-value {
            font-size: 2.2em;
            font-weight: bold;
            color: #2a5298;
            margin-bottom: 5px;
        }
        .stat-label {
            color: #666;
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .nodes-section {
            margin-bottom: 40px;
        }
        .section-title {
            font-size: 1.5em;
            color: #1e3c72;
            margin-bottom: 20px;
            border-left: 4px solid #2a5298;
            padding-left: 15px;
        }
        .node-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 15px;
        }
        .node-card {
            background: white;
            border: 1px solid #e0e6ed;
            border-radius: 8px;
            padding: 20px;
            position: relative;
        }
        .node-status {
            position: absolute;
            top: 15px;
            right: 15px;
            width: 12px;
            height: 12px;
            border-radius: 50%;
        }
        .status-healthy { background: #28a745; }
        .status-degraded { background: #ffc107; }
        .status-down { background: #dc3545; }
        .node-url {
            font-weight: bold;
            color: #1e3c72;
            margin-bottom: 10px;
        }
        .node-details {
            font-size: 0.9em;
            color: #666;
            line-height: 1.5;
        }
        .miners-section {
            margin-bottom: 40px;
        }
        .miners-table {
            width: 100%;
            border-collapse: collapse;
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        .miners-table th {
            background: #f8f9fa;
            padding: 15px;
            text-align: left;
            font-weight: 600;
            color: #333;
            border-bottom: 1px solid #e0e6ed;
        }
        .miners-table td {
            padding: 12px 15px;
            border-bottom: 1px solid #f0f0f0;
        }
        .miners-table tr:hover {
            background: #f8f9fa;
        }
        .hardware-tag {
            background: #e3f2fd;
            color: #1565c0;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.8em;
            font-weight: 500;
        }
        .footer {
            text-align: center;
            color: #666;
            font-size: 0.9em;
            padding-top: 20px;
            border-top: 1px solid #e0e6ed;
        }
        .refresh-info {
            background: #e8f4f8;
            border: 1px solid #b8daff;
            color: #0c5460;
            padding: 10px;
            border-radius: 6px;
            margin-bottom: 20px;
            text-align: center;
        }
        @media (max-width: 768px) {
            body { padding: 10px; }
            .container { padding: 20px; }
            .header h1 { font-size: 2em; }
            .stats-grid { grid-template-columns: 1fr; }
            .miners-table { font-size: 0.9em; }
            .miners-table th, .miners-table td { padding: 8px; }
        }
    </style>
    <script>
        let countdownInterval;

        function startCountdown() {
            let seconds = 60;
            const countdownEl = document.getElementById('countdown');

            countdownInterval = setInterval(() => {
                seconds--;
                if (countdownEl) {
                    countdownEl.textContent = seconds;
                }

                if (seconds <= 0) {
                    location.reload();
                }
            }, 1000);
        }

        window.onload = function() {
            startCountdown();
        };
    </script>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>RustChain Network Status</h1>
            <p>Proof-of-Antiquity blockchain rewarding vintage hardware with higher mining multipliers</p>
        </div>

        <div class="refresh-info">
            ⏱️ Auto-refresh in <span id="countdown">60</span> seconds | Last updated: {{ last_updated }}
        </div>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value">{{ total_nodes }}</div>
                <div class="stat-label">Active Nodes</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{{ total_miners }}</div>
                <div class="stat-label">Active Miners</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{{ current_epoch }}</div>
                <div class="stat-label">Current Epoch</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{{ network_hash_rate }}</div>
                <div class="stat-label">Network Hash Rate</div>
            </div>
        </div>

        <div class="nodes-section">
            <h2 class="section-title">Node Status</h2>
            <div class="node-grid">
                {% for node in nodes %}
                <div class="node-card">
                    <div class="node-status status-{{ node.status }}"></div>
                    <div class="node-url">{{ node.url }}</div>
                    <div class="node-details">
                        <strong>Status:</strong> {{ node.status_text }}<br>
                        <strong>Response Time:</strong> {{ node.response_time }}ms<br>
                        <strong>Block Height:</strong> {{ node.block_height }}<br>
                        <strong>Version:</strong> {{ node.version }}
                    </div>
                </div>
                {% endfor %}
            </div>
        </div>

        <div class="miners-section">
            <h2 class="section-title">Active Miners ({{ miners|length }})</h2>
            {% if miners %}
            <table class="miners-table">
                <thead>
                    <tr>
                        <th>Miner ID</th>
                        <th>Hardware</th>
                        <th>Multiplier</th>
                        <th>RTC Balance</th>
                        <th>Last Seen</th>
                    </tr>
                </thead>
                <tbody>
                    {% for miner in miners %}
                    <tr>
                        <td>{{ miner.miner_id[:12] }}...</td>
                        <td><span class="hardware-tag">{{ miner.hardware_type }}</span></td>
                        <td>{{ miner.multiplier }}x</td>
                        <td>{{ miner.balance_rtc }} RTC</td>
                        <td>{{ miner.last_seen }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            {% else %}
            <p style="text-align: center; color: #666; padding: 40px;">No active miners found.</p>
            {% endif %}
        </div>

        <div class="footer">
            <p>
                <strong>RustChain</strong> - Proof-of-Antiquity Blockchain |
                <a href="https://github.com/Scottcjn/Rustchain" target="_blank">GitHub</a> |
                <a href="https://50.28.86.131/explorer" target="_blank">Explorer</a>
            </p>
            <p style="margin-top: 10px;">
                Network rewards vintage hardware (PowerPC G4/G5, 68K Macs, SPARC) with mining multipliers up to 50x
            </p>
        </div>
    </div>
</body>
</html>
"""


def init_database():
    """Initialize SQLite database for caching network data."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS node_status (
                url TEXT PRIMARY KEY,
                status TEXT,
                response_time INTEGER,
                block_height INTEGER,
                version TEXT,
                last_checked TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS network_stats (
                id INTEGER PRIMARY KEY,
                total_miners INTEGER,
                current_epoch INTEGER,
                hash_rate TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)


def check_node_health(node_url, timeout=10):
    """Check health status of a RustChain node."""
    try:
        start_time = time.time()
        response = requests.get(f"{node_url}/health", timeout=timeout, verify=False)
        response_time = int((time.time() - start_time) * 1000)

        if response.ok:
            health_data = response.json()
            return {
                'status': 'healthy',
                'response_time': response_time,
                'block_height': health_data.get('block_height', 0),
                'version': health_data.get('version', 'Unknown')
            }
        else:
            return {
                'status': 'degraded',
                'response_time': response_time,
                'block_height': 0,
                'version': 'Unknown'
            }
    except Exception:
        return {
            'status': 'down',
            'response_time': 0,
            'block_height': 0,
            'version': 'Unknown'
        }


def get_miners_data(node_url, timeout=10):
    """Fetch active miners from node API."""
    try:
        response = requests.get(f"{node_url}/api/miners", timeout=timeout, verify=False)
        if response.ok:
            return response.json()
        return []
    except Exception:
        return []


def get_epoch_info(node_url, timeout=10):
    """Get current epoch information."""
    try:
        response = requests.get(f"{node_url}/api/epoch", timeout=timeout, verify=False)
        if response.ok:
            return response.json()
        return {}
    except Exception:
        return {}


def fetch_network_data(nodes=None):
    """Fetch comprehensive network data from all nodes."""
    if nodes is None:
        nodes = DEFAULT_NODES

    node_data = []
    all_miners = []
    epoch_info = {}

    # Check each node
    for node_url in nodes:
        health = check_node_health(node_url)
        node_info = {
            'url': node_url,
            'status': health['status'],
            'status_text': health['status'].title(),
            'response_time': health['response_time'],
            'block_height': health['block_height'],
            'version': health['version']
        }
        node_data.append(node_info)

        # Get miners data from healthy nodes
        if health['status'] == 'healthy':
            miners = get_miners_data(node_url)
            if miners and len(miners) > len(all_miners):
                all_miners = miners

            # Get epoch info
            if not epoch_info:
                epoch_info = get_epoch_info(node_url)

    # Process miners data
    processed_miners = []
    for miner in all_miners:
        processed_miners.append({
            'miner_id': miner.get('miner_id', 'Unknown'),
            'hardware_type': miner.get('hardware_type', 'Unknown'),
            'multiplier': miner.get('mining_multiplier', 1),
            'balance_rtc': miner.get('amount_rtc', 0),
            'last_seen': miner.get('last_active', 'Unknown')
        })

    return {
        'nodes': node_data,
        'miners': processed_miners,
        'epoch_info': epoch_info,
        'total_nodes': len([n for n in node_data if n['status'] == 'healthy']),
        'total_miners': len(processed_miners)
    }


def cache_network_data(network_data):
    """Cache network data in SQLite database."""
    with sqlite3.connect(DB_PATH) as conn:
        # Cache node status
        for node in network_data['nodes']:
            conn.execute("""
                INSERT OR REPLACE INTO node_status
                (url, status, response_time, block_height, version)
                VALUES (?, ?, ?, ?, ?)
            """, (
                node['url'], node['status'], node['response_time'],
                node['block_height'], node['version']
            ))

        # Cache network stats
        conn.execute("DELETE FROM network_stats")
        conn.execute("""
            INSERT INTO network_stats
            (total_miners, current_epoch, hash_rate)
            VALUES (?, ?, ?)
        """, (
            network_data['total_miners'],
            network_data['epoch_info'].get('current_epoch', 0),
            network_data['epoch_info'].get('hash_rate', 'N/A')
        ))


def load_cached_data():
    """Load cached network data from database."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            # Load node data
            nodes_cursor = conn.execute("SELECT * FROM node_status ORDER BY url")
            nodes = []
            for row in nodes_cursor:
                nodes.append({
                    'url': row[0],
                    'status': row[1],
                    'status_text': row[1].title(),
                    'response_time': row[2],
                    'block_height': row[3],
                    'version': row[4]
                })

            # Load network stats
            stats_cursor = conn.execute("SELECT * FROM network_stats ORDER BY id DESC LIMIT 1")
            stats_row = stats_cursor.fetchone()

            if stats_row:
                return {
                    'nodes': nodes,
                    'miners': [],
                    'total_miners': stats_row[1],
                    'current_epoch': stats_row[2],
                    'hash_rate': stats_row[3]
                }
    except Exception:
        pass

    return None


def generate_status_page(use_cache=False):
    """Generate HTML status page with current network data."""
    if use_cache:
        network_data = load_cached_data()
        if network_data is None:
            network_data = fetch_network_data()
            cache_network_data(network_data)
    else:
        network_data = fetch_network_data()
        cache_network_data(network_data)

    # Calculate network hash rate estimate
    active_miners = network_data['total_miners']
    estimated_hashrate = f"{active_miners * 2.5:.1f} KH/s" if active_miners > 0 else "N/A"

    template_data = {
        'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC'),
        'total_nodes': network_data['total_nodes'],
        'total_miners': network_data['total_miners'],
        'current_epoch': network_data.get('epoch_info', {}).get('current_epoch', 'N/A'),
        'network_hash_rate': estimated_hashrate,
        'nodes': network_data['nodes'],
        'miners': network_data.get('miners', [])
    }

    return render_template_string(STATUS_PAGE_TEMPLATE, **template_data)


def save_status_page(filename="rustchain_status.html", use_cache=False):
    """Generate and save status page to HTML file."""
    html_content = generate_status_page(use_cache=use_cache)

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"Status page saved to {filename}")
    return filename


if __name__ == "__main__":
    # Initialize database
    init_database()

    # Generate fresh status page
    output_file = save_status_page("rustchain_network_status.html", use_cache=False)
    print(f"Network status page generated: {output_file}")

    # Also generate a cached version for faster loading
    cached_file = save_status_page("rustchain_status_cached.html", use_cache=True)
    print(f"Cached status page: {cached_file}")
