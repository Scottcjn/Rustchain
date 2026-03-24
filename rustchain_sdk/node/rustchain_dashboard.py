#!/usr/bin/env python3
"""
RustChain Mining Dashboard - Enhanced
--------------------------------------
Features: System stats, network age, wallet search, SSL ready
"""
import sqlite3
import json
import time
import psutil
import os
from datetime import datetime, timedelta
from flask import Flask, send_from_directory, render_template_string, jsonify, request
import requests

app = Flask(__name__)

DOWNLOAD_DIR = "/root/rustchain/downloads"

# Configuration
DB_PATH = "/root/rustchain/rustchain_v2.db"
NODE_API = "http://localhost:8088"

# HTML Template
DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>RustChain Mining Dashboard</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #fff;
            padding: 20px;
            min-height: 100vh;
        }
        .container { max-width: 1600px; margin: 0 auto; }
        .header {
            text-align: center;
            margin-bottom: 40px;
            padding: 30px;
            background: rgba(255,255,255,0.1);
            border-radius: 15px;
            backdrop-filter: blur(10px);
        }
        .header h1 { font-size: 3em; margin-bottom: 10px; }
        .header p { font-size: 1.2em; opacity: 0.9; }

        /* Wallet Search */
        .search-box {
            background: rgba(255,255,255,0.15);
            padding: 20px;
            border-radius: 15px;
            margin-bottom: 30px;
            backdrop-filter: blur(10px);
        }
        .search-input {
            width: 70%;
            padding: 15px;
            font-size: 1em;
            border: 2px solid rgba(255,255,255,0.3);
            border-radius: 10px;
            background: rgba(0,0,0,0.3);
            color: #fff;
            margin-right: 10px;
        }
        .search-button {
            padding: 15px 30px;
            font-size: 1em;
            border: none;
            border-radius: 10px;
            background: #10b981;
            color: #fff;
            cursor: pointer;
            font-weight: 600;
        }
        .search-button:hover { background: #059669; }
        .search-result {
            margin-top: 15px;
            padding: 15px;
            background: rgba(0,0,0,0.3);
            border-radius: 10px;
            display: none;
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }
        .stat-card {
            background: rgba(255,255,255,0.15);
            padding: 25px;
            border-radius: 15px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.2);
        }
        .stat-card h3 { font-size: 0.9em; opacity: 0.8; margin-bottom: 10px; }
        .stat-card .value { font-size: 2.2em; font-weight: bold; }
        .stat-card .label { font-size: 0.8em; opacity: 0.7; margin-top: 5px; }

        .section {
            background: rgba(255,255,255,0.1);
            padding: 30px;
            border-radius: 15px;
            margin-bottom: 30px;
            backdrop-filter: blur(10px);
        }
        .section h2 {
            font-size: 1.8em;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 2px solid rgba(255,255,255,0.2);
        }

        table {
            width: 100%;
            border-collapse: collapse;
            background: rgba(0,0,0,0.2);
            border-radius: 10px;
            overflow: hidden;
        }
        th, td {
            padding: 15px;
            text-align: left;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        th {
            background: rgba(0,0,0,0.3);
            font-weight: 600;
            text-transform: uppercase;
            font-size: 0.9em;
        }
        tr:hover { background: rgba(255,255,255,0.05); }

        .badge {
            display: inline-block;
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 0.85em;
            font-weight: 600;
            background: rgba(255,255,255,0.2);
        }
        .badge-active { background: #10b981; }
        .badge-classic { background: #f59e0b; }
        .badge-retro { background: #3b82f6; }
        .badge-ancient { background: #8b5cf6; }
        .badge-modern { background: #6b7280; }

        .mono { font-family: 'Courier New', monospace; font-size: 0.9em; }
        .green { color: #10b981; }
        .orange { color: #f59e0b; }
        .blue { color: #3b82f6; }

        .pulse {
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }

        .footer {
            text-align: center;
            margin-top: 40px;
            padding: 20px;
            opacity: 0.7;
            font-size: 0.9em;
        }

        .system-stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin-top: 20px;
        }
        .sys-stat {
            background: rgba(0,0,0,0.3);
            padding: 15px;
            border-radius: 10px;
            text-align: center;
        }
        .sys-stat .label { font-size: 0.8em; opacity: 0.8; margin-bottom: 5px; }
        .sys-stat .value { font-size: 1.8em; font-weight: bold; }
    </style>
    <script>
        function updateDashboard() {
            fetch('/api/stats')
                .then(r => r.json())
                .then(data => {
                    // Update mining stats
                    document.getElementById('enrolled-miners').textContent = data.enrolled_miners;
                    document.getElementById('current-epoch').textContent = data.current_epoch;
                    document.getElementById('epoch-pot').textContent = data.epoch_pot.toFixed(2);
                    document.getElementById('total-balance').textContent = data.total_balance.toFixed(2);

                    // Update system stats
                    if (data.system_stats) {
                        document.getElementById('sys-cpu').textContent = data.system_stats.cpu + '%';
                        document.getElementById('sys-mem').textContent = data.system_stats.memory + '%';
                        document.getElementById('sys-disk').textContent = data.system_stats.disk + '%';
                        document.getElementById('sys-uptime').textContent = data.system_stats.uptime;
                        document.getElementById('sys-load').textContent = data.system_stats.load_avg;
                    }

                    // Update miners table
                    const minersTable = document.getElementById('miners-tbody');
                    minersTable.innerHTML = data.active_miners.map(m => `
                        <tr>
                            <td class="mono">${m.wallet_short}...</td>
                            <td><span class="badge badge-${m.arch}">${m.arch.toUpperCase()}</span></td>
                            <td><strong>${m.weight}x</strong></td>
                            <td class="green">${m.balance.toFixed(6)} RTC</td>
                            <td class="mono">${m.last_seen}</td>
                            <td class="blue">${m.age_on_network || 'New'}</td>
                            <td><span class="badge badge-active pulse">ACTIVE</span></td>
                        </tr>
                    `).join('');

                    // Update recent blocks
                    const blocksTable = document.getElementById('blocks-tbody');
                    blocksTable.innerHTML = data.recent_blocks.map(b => `
                        <tr>
                            <td><strong>${b.height}</strong></td>
                            <td class="mono">${b.hash_short}...</td>
                            <td>${b.timestamp}</td>
                            <td><span class="badge">${b.miners_count} miners</span></td>
                            <td class="green">${b.reward} RTC</td>
                        </tr>
                    `).join('');

                    document.getElementById('last-update').textContent = new Date().toLocaleTimeString();
                });
        }

        function searchWallet() {
            const wallet = document.getElementById('wallet-search').value.trim();
            if (!wallet) return;

            fetch(`/api/wallet/${wallet}`)
                .then(r => r.json())
                .then(data => {
                    const resultDiv = document.getElementById('search-result');
                    if (data.found) {
                        resultDiv.innerHTML = `
                            <h3>✅ Wallet Found</h3>
                            <p><strong>Address:</strong> <span class="mono">${data.wallet}</span></p>
                            <p><strong>Balance:</strong> <span class="green">${data.balance} RTC</span></p>
                            <p><strong>Weight:</strong> ${data.weight}x (${data.tier})</p>
                            <p><strong>Age on Network:</strong> ${data.age_on_network || 'Unknown'}</p>
                            <p><strong>Status:</strong> ${data.enrolled ? '✅ Enrolled in current epoch' : '⏸️ Not currently enrolled'}</p>
                            <p><strong>Last Seen:</strong> ${data.last_seen || 'Never'}</p>
                        `;
                    } else {
                        resultDiv.innerHTML = `
                            <h3>❌ Wallet Not Found</h3>
                            <p>No miner found with address: <span class="mono">${wallet}</span></p>
                        `;
                    }
                    resultDiv.style.display = 'block';
                })
                .catch(err => {
                    document.getElementById('search-result').innerHTML = `<h3>❌ Error</h3><p>${err}</p>`;
                    document.getElementById('search-result').style.display = 'block';
                });
        }

        // Update every 10 seconds
        setInterval(updateDashboard, 10000);
        updateDashboard();
    </script>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>⛏️ RustChain Mining Dashboard</h1>
            <p>Real-time mining statistics and network monitoring</p>
        </div>

        <!-- Wallet Search -->
        <div class="search-box">
            <h2 style="margin-bottom: 15px;">🔍 Wallet Balance Lookup</h2>
            <input type="text" id="wallet-search" class="search-input" placeholder="Enter wallet address..." />
            <button class="search-button" onclick="searchWallet()">Search</button>
            <div id="search-result" class="search-result"></div>
        </div>

        <!-- Mining Stats -->
        <div class="stats-grid">
            <div class="stat-card">
                <h3>Active Miners</h3>
                <div class="value" id="enrolled-miners">0</div>
                <div class="label">Currently enrolled</div>
            </div>
            <div class="stat-card">
                <h3>Current Epoch</h3>
                <div class="value" id="current-epoch">0</div>
                <div class="label">144 blocks per epoch</div>
            </div>
            <div class="stat-card">
                <h3>Epoch Pot</h3>
                <div class="value" id="epoch-pot">0.00</div>
                <div class="label">RTC per block</div>
            </div>
            <div class="stat-card">
                <h3>Total Mined</h3>
                <div class="value" id="total-balance">0.00</div>
                <div class="label">RTC distributed</div>
            </div>
        </div>

        <!-- System Stats -->
        <div class="section">
            <h2>📊 System Statistics</h2>
            <div class="system-stats">
                <div class="sys-stat">
                    <div class="label">CPU Usage</div>
                    <div class="value" id="sys-cpu">0%</div>
                </div>
                <div class="sys-stat">
                    <div class="label">Memory</div>
                    <div class="value" id="sys-mem">0%</div>
                </div>
                <div class="sys-stat">
                    <div class="label">Disk</div>
                    <div class="value" id="sys-disk">0%</div>
                </div>
                <div class="sys-stat">
                    <div class="label">Uptime</div>
                    <div class="value" id="sys-uptime">-</div>
                </div>
                <div class="sys-stat">
                    <div class="label">Load Avg</div>
                    <div class="value" id="sys-load">-</div>
                </div>
            </div>
        </div>

        <!-- Active Miners -->
        <div class="section">
            <h2>🖥️ Active Miners</h2>
            <table>
                <thead>
                    <tr>
                        <th>Wallet</th>
                        <th>Tier</th>
                        <th>Weight</th>
                        <th>Balance</th>
                        <th>Last Seen</th>
                        <th>Network Age</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody id="miners-tbody">
                    <tr><td colspan="7" style="text-align:center">Loading...</td></tr>
                </tbody>
            </table>
        </div>

        <!-- Recent Blocks -->
        <div class="section">
            <h2>📦 Recent Epochs</h2>
            <table>
                <thead>
                    <tr>
                        <th>Epoch</th>
                        <th>Hash</th>
                        <th>Timestamp</th>
                        <th>Miners</th>
                        <th>Reward</th>
                    </tr>
                </thead>
                <tbody id="blocks-tbody">
                    <tr><td colspan="5" style="text-align:center">Loading...</td></tr>
                </tbody>
            </table>
        </div>

        <div class="footer">
            Auto-refreshing every 10 seconds | Last update: <span id="last-update">-</span><br>
            RustChain v2.2.1 | Proof of Antiquity | Block Time: 10 minutes<br>
            🔒 Secure Connection
        </div>
    </div>

        <div class="section">
            <h2 style="text-align: center; margin-bottom: 30px;">📥 Download Miners</h2>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-top: 20px;">
                <div style="background: rgba(16, 185, 129, 0.2); padding: 20px; border-radius: 10px; border: 2px solid #10b981;">
                    <h3 style="color: #10b981; margin-bottom: 10px;">🦀 All Platforms</h3>
                    <p style="font-size: 0.9em; margin-bottom: 15px;">Complete package (18 KB)</p>
                    <a href="/downloads/rustchain_miners_v2.2.1.zip" style="display: block; background: #10b981; color: #000; padding: 10px 20px; text-align: center; text-decoration: none; border-radius: 5px; font-weight: bold;">Download ZIP</a>
                </div>
                <div style="background: rgba(59, 130, 246, 0.2); padding: 20px; border-radius: 10px; border: 2px solid #3b82f6;">
                    <h3 style="color: #3b82f6; margin-bottom: 10px;">🍎 PowerPC G4/G5</h3>
                    <p style="font-size: 0.9em; margin-bottom: 15px;">2.5x mining power!</p>
                    <a href="/downloads/rustchain_powerpc_g4_miner.py" style="display: block; background: #3b82f6; color: #fff; padding: 10px 20px; text-align: center; text-decoration: none; border-radius: 5px; font-weight: bold;">Download</a>
                </div>
                <div style="background: rgba(139, 92, 246, 0.2); padding: 20px; border-radius: 10px; border: 2px solid #8b5cf6;">
                    <h3 style="color: #8b5cf6; margin-bottom: 10px;">💻 Mac (Intel/M1)</h3>
                    <p style="font-size: 0.9em; margin-bottom: 15px;">Universal binary</p>
                    <a href="/downloads/rustchain_mac_universal_miner.py" style="display: block; background: #8b5cf6; color: #fff; padding: 10px 20px; text-align: center; text-decoration: none; border-radius: 5px; font-weight: bold;">Download</a>
                </div>
                <div style="background: rgba(236, 72, 153, 0.2); padding: 20px; border-radius: 10px; border: 2px solid #ec4899;">
                    <h3 style="color: #ec4899; margin-bottom: 10px;">🐧 Linux</h3>
                    <p style="font-size: 0.9em; margin-bottom: 15px;">x86_64, ARM, RISC-V</p>
                    <a href="/downloads/rustchain_linux_miner.py" style="display: block; background: #ec4899; color: #fff; padding: 10px 20px; text-align: center; text-decoration: none; border-radius: 5px; font-weight: bold;">Download</a>
                </div>
                <div style="background: rgba(245, 158, 11, 0.2); padding: 20px; border-radius: 10px; border: 2px solid #f59e0b;">
                    <h3 style="color: #f59e0b; margin-bottom: 10px;">🪟 Windows</h3>
                    <p style="font-size: 0.9em; margin-bottom: 15px;">Windows 10/11 64-bit</p>
                    <a href="/downloads/RustChain-Windows-Installer-v2.2.1.zip" style="display: block; background: #f59e0b; color: #000; padding: 10px 20px; text-align: center; text-decoration: none; border-radius: 5px; font-weight: bold;">Download Installer</a>
                </div>
            </div>
            <div style="margin-top: 30px; padding: 20px; background: rgba(255,255,255,0.1); border-radius: 10px;">
                <h3 style="margin-bottom: 15px;">🚀 Quick Start</h3>
                <p>1. Install Python 3: <code style="background: rgba(0,0,0,0.3); padding: 5px 10px; border-radius: 5px;">python3 --version</code></p>
                <p>2. Install requests: <code style="background: rgba(0,0,0,0.3); padding: 5px 10px; border-radius: 5px;">pip3 install requests</code></p>
                <p>3. Run miner: <code style="background: rgba(0,0,0,0.3); padding: 5px 10px; border-radius: 5px;">python3 rustchain_linux_miner.py</code></p>
            </div>
        </div>

    </body>
</html>
"""

@app.route('/')
def dashboard():
    """Main dashboard page"""
    return render_template_string(DASHBOARD_HTML)

@app.route('/api/stats')
def api_stats():
    """Get current mining and system statistics"""
    try:
        # Get epoch info from node API
        epoch_resp = requests.get(f"{NODE_API}/epoch", timeout=5)
        epoch_data = epoch_resp.json()

        # Get stats from node API
        stats_resp = requests.get(f"{NODE_API}/api/stats", timeout=5)
        stats_data = stats_resp.json()

        # Get system stats
        cpu_percent = psutil.cpu_percent(interval=1)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        uptime_seconds = time.time() - psutil.boot_time()
        uptime_str = format_uptime(uptime_seconds)
        load_avg = os.getloadavg()[0]

        system_stats = {
            'cpu': round(cpu_percent, 1),
            'memory': round(mem.percent, 1),
            'disk': round(disk.percent, 1),
            'uptime': uptime_str,
            'load_avg': f"{load_avg:.2f}"
        }

        # Query database for detailed miner info
        with sqlite3.connect(DB_PATH) as conn:
            # Get active miners in current epoch with first seen date
            miners = conn.execute("""
                SELECT
                    e.miner_pk,
                    e.weight,
                    b.balance_rtc,
                    MAX(a.ts_ok) as last_attest,
                    MIN(a.ts_ok) as first_attest
                FROM epoch_enroll e
                LEFT JOIN balances b ON e.miner_pk = b.miner_pk
                LEFT JOIN miner_attest_recent a ON e.miner_pk = a.miner
                WHERE e.epoch = ?
                GROUP BY e.miner_pk
                ORDER BY e.weight DESC, b.balance_rtc DESC
                LIMIT 50
            """, (epoch_data['epoch'],)).fetchall()

            active_miners = []
            for miner in miners:
                wallet = miner[0]
                weight = miner[1]
                balance = miner[2] or 0.0
                last_seen = miner[3] or int(time.time())
                first_seen = miner[4]

                # Determine tier from weight
                if weight >= 3.0:
                    arch = "ancient"
                elif weight >= 2.5:
                    arch = "classic"
                elif weight >= 1.5:
                    arch = "retro"
                else:
                    arch = "modern"

                last_seen_str = datetime.fromtimestamp(last_seen).strftime('%H:%M:%S')

                # Calculate age on network
                age_on_network = ""
                if first_seen:
                    age_days = (time.time() - first_seen) / 86400
                    if age_days < 1:
                        age_on_network = f"{int(age_days * 24)}h"
                    elif age_days < 7:
                        age_on_network = f"{int(age_days)}d"
                    else:
                        age_on_network = f"{int(age_days / 7)}w"

                active_miners.append({
                    'wallet': wallet,
                    'wallet_short': wallet[:16],
                    'weight': weight,
                    'balance': balance,
                    'arch': arch,
                    'last_seen': last_seen_str,
                    'age_on_network': age_on_network
                })

            # Get recent epoch activity
            recent_activity = conn.execute("""
                SELECT
                    epoch,
                    COUNT(DISTINCT miner_pk) as miners,
                    SUM(weight) as total_weight
                FROM epoch_enroll
                GROUP BY epoch
                ORDER BY epoch DESC
                LIMIT 10
            """).fetchall()

            recent_blocks = []
            for idx, activity in enumerate(recent_activity):
                epoch_num = activity[0]
                miners_count = activity[1]
                total_weight = activity[2] or 1.0

                reward_per_block = 1.5

                recent_blocks.append({
                    'height': epoch_num,
                    'hash': f"{epoch_num:08x}",
                    'hash_short': f"{epoch_num:08x}",
                    'timestamp': f"Epoch {epoch_num}",
                    'miners_count': miners_count,
                    'reward': reward_per_block
                })

            # Get total distributed balance
            total_balance = conn.execute(
                "SELECT SUM(balance_rtc) FROM balances"
            ).fetchone()[0] or 0.0

        return jsonify({
            'enrolled_miners': epoch_data['enrolled_miners'],
            'current_epoch': epoch_data['epoch'],
            'epoch_pot': epoch_data['epoch_pot'],
            'total_balance': total_balance,
            'active_miners': active_miners,
            'recent_blocks': recent_blocks,
            'system_stats': system_stats,
            'timestamp': int(time.time())
        })

    except Exception as e:
        print(f"Error in api_stats: {e}")
        return jsonify({
            'enrolled_miners': 0,
            'current_epoch': 0,
            'epoch_pot': 0.0,
            'total_balance': 0.0,
            'active_miners': [],
            'recent_blocks': [],
            'system_stats': {},
            'error': str(e)
        }), 500

@app.route('/api/wallet/<wallet_address>')
def api_wallet_lookup(wallet_address):
    """Look up wallet balance and info"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            # Get balance
            balance_row = conn.execute(
                "SELECT balance_rtc FROM balances WHERE miner_pk = ?",
                (wallet_address,)
            ).fetchone()

            balance = balance_row[0] if balance_row else 0.0

            # Get enrollment info
            enrollment = conn.execute("""
                SELECT epoch, weight
                FROM epoch_enroll
                WHERE miner_pk = ?
                ORDER BY epoch DESC
                LIMIT 1
            """, (wallet_address,)).fetchone()

            # Get attestation info for age
            attestation = conn.execute("""
                SELECT MIN(ts_ok) as first_seen, MAX(ts_ok) as last_seen
                FROM miner_attest_recent
                WHERE miner = ?
            """, (wallet_address,)).fetchone()

            if balance_row or enrollment or (attestation and attestation[0]):
                weight = enrollment[1] if enrollment else 1.0
                current_epoch = enrollment[0] if enrollment else 0

                # Get current epoch
                epoch_resp = requests.get(f"{NODE_API}/epoch", timeout=5)
                epoch_data = epoch_resp.json()

                enrolled = (current_epoch == epoch_data['epoch']) if enrollment else False

                # Determine tier
                if weight >= 3.0:
                    tier = "Ancient"
                elif weight >= 2.5:
                    tier = "Classic"
                elif weight >= 1.5:
                    tier = "Retro"
                else:
                    tier = "Modern"

                # Calculate age
                age_on_network = ""
                first_seen = attestation[0] if attestation else None
                last_seen = attestation[1] if attestation else None

                if first_seen:
                    age_days = (time.time() - first_seen) / 86400
                    if age_days < 1:
                        age_on_network = f"{int(age_days * 24)} hours"
                    else:
                        age_on_network = f"{int(age_days)} days"

                last_seen_str = datetime.fromtimestamp(last_seen).strftime('%Y-%m-%d %H:%M:%S') if last_seen else "Never"

                return jsonify({
                    'found': True,
                    'wallet': wallet_address,
                    'balance': balance,
                    'weight': weight,
                    'tier': tier,
                    'enrolled': enrolled,
                    'age_on_network': age_on_network,
                    'last_seen': last_seen_str
                })
            else:
                return jsonify({
                    'found': False,
                    'wallet': wallet_address
                })

    except Exception as e:
        print(f"Error in wallet lookup: {e}")
        return jsonify({'error': str(e)}), 500

def format_uptime(seconds):
    """Format uptime in human-readable format"""
    days = int(seconds // 86400)
    hours = int((seconds % 86400) // 3600)
    if days > 0:
        return f"{days}d {hours}h"
    elif hours > 0:
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"
    else:
        minutes = int(seconds // 60)
        return f"{minutes}m"


@app.route('/downloads/<path:filename>')
def download_file(filename):
    from flask import send_from_directory
    return send_from_directory(DOWNLOAD_DIR, filename, as_attachment=True)

if __name__ == '__main__':
    # Run on all interfaces, port 8099 (dashboard)
    # For SSL: use nginx reverse proxy or flask-tls
    app.run(host='0.0.0.0', port=8099, debug=False)
