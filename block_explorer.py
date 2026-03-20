# SPDX-License-Identifier: MIT

from flask import Flask, render_template_string, jsonify, request
import sqlite3
import json
import time
from datetime import datetime, timedelta
import requests
from threading import Thread
import logging

app = Flask(__name__)
app.config['SECRET_KEY'] = 'rustchain-explorer-key'

DB_PATH = 'rustchain.db'
API_BASE = 'https://explorer.rustchain.org/api'

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_db():
    """Initialize the database with required tables"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS miners (
                id TEXT PRIMARY KEY,
                architecture TEXT,
                antiquity_multiplier REAL,
                last_attestation INTEGER,
                status TEXT,
                updated_at INTEGER
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS blocks (
                height INTEGER PRIMARY KEY,
                hash TEXT,
                timestamp INTEGER,
                miner_id TEXT,
                tx_count INTEGER
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS agents (
                id TEXT PRIMARY KEY,
                name TEXT,
                performance_score REAL,
                jobs_completed INTEGER,
                rtc_earned REAL,
                status TEXT
            )
        ''')
        conn.commit()

def fetch_api_data():
    """Background task to fetch and cache API data"""
    while True:
        try:
            # Fetch miners data
            resp = requests.get(f'{API_BASE}/miners', timeout=10)
            if resp.status_code == 200:
                miners_data = resp.json()
                with sqlite3.connect(DB_PATH) as conn:
                    for miner in miners_data.get('miners', []):
                        conn.execute('''
                            INSERT OR REPLACE INTO miners
                            (id, architecture, antiquity_multiplier, last_attestation, status, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?)
                        ''', (
                            miner.get('id'),
                            miner.get('architecture'),
                            miner.get('antiquity_multiplier', 1.0),
                            miner.get('last_attestation', 0),
                            miner.get('status', 'unknown'),
                            int(time.time())
                        ))
                    conn.commit()

            # Fetch agent stats
            resp = requests.get(f'{API_BASE}/agent/stats', timeout=10)
            if resp.status_code == 200:
                agent_data = resp.json()
                with sqlite3.connect(DB_PATH) as conn:
                    for agent in agent_data.get('agents', []):
                        conn.execute('''
                            INSERT OR REPLACE INTO agents
                            (id, name, performance_score, jobs_completed, rtc_earned, status)
                            VALUES (?, ?, ?, ?, ?, ?)
                        ''', (
                            agent.get('id'),
                            agent.get('name'),
                            agent.get('performance_score', 0.0),
                            agent.get('jobs_completed', 0),
                            agent.get('rtc_earned', 0.0),
                            agent.get('status', 'inactive')
                        ))
                    conn.commit()

        except Exception as e:
            logger.error(f"Failed to fetch API data: {e}")

        time.sleep(30)

@app.route('/')
def block_explorer():
    """Main block explorer dashboard"""
    html_template = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RustChain Block Explorer</title>
    <style>
        body { font-family: 'Segoe UI', sans-serif; margin: 0; background: #0a0a0a; color: #e0e0e0; }
        .header { background: linear-gradient(135deg, #1a1a2e, #16213e); padding: 20px; text-align: center; }
        .header h1 { margin: 0; color: #ff6b35; font-size: 2.5em; }
        .nav { background: #16213e; padding: 15px; text-align: center; }
        .nav a { color: #ff6b35; text-decoration: none; margin: 0 20px; font-weight: bold; }
        .nav a:hover { color: #fff; }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .stat-card { background: #1e1e2e; padding: 20px; border-radius: 10px; border-left: 4px solid #ff6b35; }
        .stat-card h3 { margin: 0 0 10px 0; color: #ff6b35; }
        .stat-card .value { font-size: 2em; font-weight: bold; }
        .section { background: #1e1e2e; margin: 20px 0; padding: 20px; border-radius: 10px; }
        .section h2 { color: #ff6b35; margin-top: 0; }
        .miners-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 15px; }
        .miner-card { background: #2a2a3e; padding: 15px; border-radius: 8px; border: 1px solid #444; }
        .miner-card.online { border-color: #4caf50; }
        .miner-card.offline { border-color: #f44336; }
        .arch-badge { display: inline-block; background: #ff6b35; color: #000; padding: 3px 8px; border-radius: 4px; font-size: 0.8em; font-weight: bold; margin-right: 10px; }
        .status-online { color: #4caf50; font-weight: bold; }
        .status-offline { color: #f44336; font-weight: bold; }
        .refresh-indicator { position: fixed; top: 20px; right: 20px; background: #ff6b35; color: #000; padding: 10px; border-radius: 5px; display: none; }
        .table { width: 100%; border-collapse: collapse; }
        .table th, .table td { padding: 12px; text-align: left; border-bottom: 1px solid #444; }
        .table th { background: #2a2a3e; color: #ff6b35; }
        .table tr:hover { background: #2a2a3e; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🦀 RustChain Explorer</h1>
        <p>Real-Time Blockchain Explorer & Mining Dashboard</p>
    </div>

    <div class="nav">
        <a href="#miners">Miners</a>
        <a href="#agents">Agents</a>
        <a href="#blocks">Blocks</a>
        <a href="#api">API</a>
    </div>

    <div class="refresh-indicator" id="refreshing">Refreshing...</div>

    <div class="container">
        <div class="stats-grid">
            <div class="stat-card">
                <h3>Active Miners</h3>
                <div class="value" id="active-miners">{{ active_miners }}</div>
            </div>
            <div class="stat-card">
                <h3>Total Blocks</h3>
                <div class="value" id="total-blocks">{{ total_blocks }}</div>
            </div>
            <div class="stat-card">
                <h3>Network Hash Rate</h3>
                <div class="value">{{ network_hashrate }}</div>
            </div>
            <div class="stat-card">
                <h3>Active Agents</h3>
                <div class="value" id="active-agents">{{ active_agents }}</div>
            </div>
        </div>

        <div class="section" id="miners">
            <h2>🔨 Miner Dashboard</h2>
            <div class="miners-grid" id="miners-grid">
                {% for miner in miners %}
                <div class="miner-card {{ 'online' if miner.status == 'online' else 'offline' }}">
                    <div>
                        <span class="arch-badge">{{ miner.architecture }}</span>
                        <strong>{{ miner.id[:12] }}...</strong>
                    </div>
                    <div style="margin-top: 10px;">
                        <div>Antiquity: {{ "%.2f"|format(miner.antiquity_multiplier) }}x</div>
                        <div>Status: <span class="status-{{ miner.status }}">{{ miner.status.upper() }}</span></div>
                        <div>Last Seen: {{ miner.last_seen }}</div>
                    </div>
                </div>
                {% endfor %}
            </div>
        </div>

        <div class="section" id="agents">
            <h2>🤖 Agent Economy</h2>
            <table class="table">
                <thead>
                    <tr>
                        <th>Agent ID</th>
                        <th>Name</th>
                        <th>Performance</th>
                        <th>Jobs Completed</th>
                        <th>RTC Earned</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody id="agents-table">
                    {% for agent in agents %}
                    <tr>
                        <td>{{ agent.id[:12] }}...</td>
                        <td>{{ agent.name }}</td>
                        <td>{{ "%.1f"|format(agent.performance_score) }}</td>
                        <td>{{ agent.jobs_completed }}</td>
                        <td>{{ "%.2f"|format(agent.rtc_earned) }} RTC</td>
                        <td><span class="status-{{ 'online' if agent.status == 'active' else 'offline' }}">{{ agent.status.upper() }}</span></td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>

        <div class="section" id="blocks">
            <h2>📦 Recent Blocks</h2>
            <table class="table">
                <thead>
                    <tr>
                        <th>Height</th>
                        <th>Hash</th>
                        <th>Timestamp</th>
                        <th>Miner</th>
                        <th>Transactions</th>
                    </tr>
                </thead>
                <tbody id="blocks-table">
                    {% for block in blocks %}
                    <tr>
                        <td>{{ block.height }}</td>
                        <td>{{ block.hash[:16] }}...</td>
                        <td>{{ block.timestamp_str }}</td>
                        <td>{{ block.miner_id[:12] if block.miner_id else 'Unknown' }}...</td>
                        <td>{{ block.tx_count }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>

    <script>
        function refreshData() {
            document.getElementById('refreshing').style.display = 'block';

            fetch('/api/dashboard-data')
                .then(response => response.json())
                .then(data => {
                    // Update stats
                    document.getElementById('active-miners').textContent = data.stats.active_miners;
                    document.getElementById('total-blocks').textContent = data.stats.total_blocks;
                    document.getElementById('active-agents').textContent = data.stats.active_agents;

                    // Update miners grid
                    const minersGrid = document.getElementById('miners-grid');
                    minersGrid.innerHTML = data.miners.map(miner => `
                        <div class="miner-card ${miner.status === 'online' ? 'online' : 'offline'}">
                            <div>
                                <span class="arch-badge">${miner.architecture}</span>
                                <strong>${miner.id.substring(0, 12)}...</strong>
                            </div>
                            <div style="margin-top: 10px;">
                                <div>Antiquity: ${miner.antiquity_multiplier.toFixed(2)}x</div>
                                <div>Status: <span class="status-${miner.status}">${miner.status.toUpperCase()}</span></div>
                                <div>Last Seen: ${miner.last_seen}</div>
                            </div>
                        </div>
                    `).join('');

                    document.getElementById('refreshing').style.display = 'none';
                })
                .catch(error => {
                    console.error('Refresh failed:', error);
                    document.getElementById('refreshing').style.display = 'none';
                });
        }

        // Auto-refresh every 30 seconds
        setInterval(refreshData, 30000);

        // Initial refresh after 2 seconds
        setTimeout(refreshData, 2000);
    </script>
</body>
</html>
    '''

    # Get data for initial render
    miners_data = get_miners_data()
    agents_data = get_agents_data()
    blocks_data = get_blocks_data()
    stats = get_dashboard_stats()

    return render_template_string(html_template,
                                miners=miners_data,
                                agents=agents_data,
                                blocks=blocks_data,
                                **stats)

@app.route('/api/dashboard-data')
def dashboard_data():
    """API endpoint for dashboard data updates"""
    return jsonify({
        'stats': get_dashboard_stats(),
        'miners': get_miners_data(),
        'agents': get_agents_data(),
        'blocks': get_blocks_data()
    })

def get_miners_data():
    """Get miners data from database"""
    miners = []
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute('''
                SELECT id, architecture, antiquity_multiplier, last_attestation, status
                FROM miners
                ORDER BY last_attestation DESC
                LIMIT 20
            ''')

            for row in cursor.fetchall():
                last_attestation = row[3]
                current_time = int(time.time())

                # Determine if miner is online (within last 5 minutes)
                is_online = (current_time - last_attestation) < 300

                miners.append({
                    'id': row[0],
                    'architecture': row[1] or 'Unknown',
                    'antiquity_multiplier': row[2] or 1.0,
                    'last_attestation': last_attestation,
                    'status': 'online' if is_online else 'offline',
                    'last_seen': format_timestamp(last_attestation)
                })
    except Exception as e:
        logger.error(f"Error fetching miners: {e}")

    return miners

def get_agents_data():
    """Get agents data from database"""
    agents = []
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute('''
                SELECT id, name, performance_score, jobs_completed, rtc_earned, status
                FROM agents
                ORDER BY performance_score DESC
                LIMIT 15
            ''')

            for row in cursor.fetchall():
                agents.append({
                    'id': row[0],
                    'name': row[1] or f"Agent-{row[0][:8]}",
                    'performance_score': row[2] or 0.0,
                    'jobs_completed': row[3] or 0,
                    'rtc_earned': row[4] or 0.0,
                    'status': row[5] or 'inactive'
                })
    except Exception as e:
        logger.error(f"Error fetching agents: {e}")

    return agents

def get_blocks_data():
    """Get recent blocks data"""
    blocks = []
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute('''
                SELECT height, hash, timestamp, miner_id, tx_count
                FROM blocks
                ORDER BY height DESC
                LIMIT 10
            ''')

            for row in cursor.fetchall():
                blocks.append({
                    'height': row[0],
                    'hash': row[1] or 'N/A',
                    'timestamp': row[2],
                    'timestamp_str': format_timestamp(row[2]),
                    'miner_id': row[3],
                    'tx_count': row[4] or 0
                })
    except Exception as e:
        logger.error(f"Error fetching blocks: {e}")

    return blocks

def get_dashboard_stats():
    """Get dashboard statistics"""
    stats = {
        'active_miners': 0,
        'total_blocks': 0,
        'network_hashrate': 'N/A',
        'active_agents': 0
    }

    try:
        with sqlite3.connect(DB_PATH) as conn:
            # Count active miners (online in last 5 minutes)
            current_time = int(time.time())
            cursor = conn.execute('''
                SELECT COUNT(*) FROM miners
                WHERE (? - last_attestation) < 300
            ''', (current_time,))
            stats['active_miners'] = cursor.fetchone()[0]

            # Count total blocks
            cursor = conn.execute('SELECT COUNT(*) FROM blocks')
            stats['total_blocks'] = cursor.fetchone()[0]

            # Count active agents
            cursor = conn.execute('''
                SELECT COUNT(*) FROM agents
                WHERE status = 'active'
            ''')
            stats['active_agents'] = cursor.fetchone()[0]

    except Exception as e:
        logger.error(f"Error getting stats: {e}")

    return stats

def format_timestamp(timestamp):
    """Format timestamp for display"""
    if not timestamp:
        return 'Never'

    try:
        dt = datetime.fromtimestamp(timestamp)
        now = datetime.now()
        diff = now - dt

        if diff.days > 0:
            return f"{diff.days}d ago"
        elif diff.seconds > 3600:
            return f"{diff.seconds // 3600}h ago"
        elif diff.seconds > 60:
            return f"{diff.seconds // 60}m ago"
        else:
            return "Just now"
    except:
        return 'Invalid'

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': int(time.time()),
        'service': 'block_explorer'
    })

if __name__ == '__main__':
    init_db()

    # Start background data fetcher
    data_thread = Thread(target=fetch_api_data, daemon=True)
    data_thread.start()

    app.run(host='0.0.0.0', port=5555, debug=False)
