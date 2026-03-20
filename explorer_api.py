// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

from flask import Flask, render_template_string, jsonify, request
import sqlite3
import json
import os
from datetime import datetime, timedelta

DB_PATH = "node/rustchain.db"

def create_app():
    app = Flask(__name__)
    return app

app = create_app()

@app.route('/explorer')
def explorer_dashboard():
    """Main block explorer dashboard"""
    html_template = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>RustChain Block Explorer</title>
        <style>
            body { font-family: 'Segoe UI', Arial, sans-serif; margin: 0; padding: 0; background: #0a0a0a; color: #e0e0e0; }
            .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
            .header { text-align: center; margin-bottom: 40px; }
            .header h1 { color: #ff6b35; font-size: 2.5em; margin-bottom: 10px; }
            .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 40px; }
            .stat-card { background: #1a1a1a; border: 1px solid #333; border-radius: 8px; padding: 20px; }
            .stat-card h3 { color: #ff6b35; margin-top: 0; }
            .stat-value { font-size: 2em; font-weight: bold; color: #4CAF50; }
            .miners-section { background: #1a1a1a; border-radius: 8px; padding: 20px; margin-bottom: 20px; }
            .miners-table { width: 100%; border-collapse: collapse; margin-top: 20px; }
            .miners-table th, .miners-table td { padding: 12px; text-align: left; border-bottom: 1px solid #333; }
            .miners-table th { background: #2a2a2a; color: #ff6b35; cursor: pointer; }
            .miners-table th:hover { background: #3a3a3a; }
            .arch-badge { display: inline-block; padding: 4px 8px; border-radius: 12px; font-size: 0.8em; font-weight: bold; }
            .arch-g4 { background: #1976d2; color: white; }
            .arch-g5 { background: #388e3c; color: white; }
            .arch-power8 { background: #f57c00; color: white; }
            .arch-apple { background: #616161; color: white; }
            .arch-modern { background: #7b1fa2; color: white; }
            .status-online { color: #4CAF50; font-weight: bold; }
            .status-offline { color: #f44336; font-weight: bold; }
            .multiplier-high { color: #ff6b35; font-weight: bold; }
            .refresh-btn { background: #ff6b35; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; margin-bottom: 20px; }
            .refresh-btn:hover { background: #e55a2b; }
            .hall-section { background: #1a1a1a; border-radius: 8px; padding: 20px; margin-bottom: 20px; }
            .wallet-lookup { background: #1a1a1a; border-radius: 8px; padding: 20px; margin-bottom: 20px; }
            .wallet-input { background: #2a2a2a; border: 1px solid #333; color: #e0e0e0; padding: 10px; border-radius: 4px; width: 300px; margin-right: 10px; }
            .lookup-btn { background: #4CAF50; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; }
            .lookup-btn:hover { background: #45a049; }
            .balance-result { margin-top: 10px; font-size: 1.2em; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🦀 RustChain Block Explorer</h1>
                <p>Real-Time Network Dashboard</p>
            </div>

            <div class="stats-grid">
                <div class="stat-card">
                    <h3>Active Miners</h3>
                    <div class="stat-value" id="activeMinerCount">-</div>
                </div>
                <div class="stat-card">
                    <h3>Current Epoch</h3>
                    <div class="stat-value" id="currentEpoch">-</div>
                </div>
                <div class="stat-card">
                    <h3>Total Blocks</h3>
                    <div class="stat-value" id="totalBlocks">-</div>
                </div>
                <div class="stat-card">
                    <h3>Network Hash Rate</h3>
                    <div class="stat-value" id="hashRate">-</div>
                </div>
            </div>

            <div class="wallet-lookup">
                <h3>🔍 Wallet Balance Lookup</h3>
                <input type="text" id="walletAddress" class="wallet-input" placeholder="Enter wallet address...">
                <button class="lookup-btn" onclick="lookupBalance()">Check Balance</button>
                <div id="balanceResult" class="balance-result"></div>
            </div>

            <div class="miners-section">
                <h3>🏭 Active Miners Dashboard</h3>
                <button class="refresh-btn" onclick="refreshData()">🔄 Refresh</button>
                <table class="miners-table" id="minersTable">
                    <thead>
                        <tr>
                            <th onclick="sortTable(0)">Miner ID</th>
                            <th onclick="sortTable(1)">Architecture</th>
                            <th onclick="sortTable(2)">Multiplier</th>
                            <th onclick="sortTable(3)">Last Seen</th>
                            <th onclick="sortTable(4)">Status</th>
                            <th onclick="sortTable(5)">Blocks Mined</th>
                        </tr>
                    </thead>
                    <tbody id="minersTableBody">
                        <tr><td colspan="6" style="text-align: center;">Loading miners...</td></tr>
                    </tbody>
                </table>
            </div>

            <div class="hall-section">
                <h3>🏆 Hall of Rust - Top Performers</h3>
                <div id="hallOfRust">Loading hall of rust...</div>
            </div>
        </div>

        <script>
            let miners = [];
            let sortColumn = -1;
            let sortDirection = 1;

            async function fetchMiners() {
                try {
                    const response = await fetch('/api/miners');
                    const data = await response.json();
                    miners = data.miners || [];
                    renderMinersTable();
                } catch (error) {
                    console.error('Error fetching miners:', error);
                    document.getElementById('minersTableBody').innerHTML = '<tr><td colspan="6" style="text-align: center; color: #f44336;">Failed to load miners</td></tr>';
                }
            }

            async function fetchStats() {
                try {
                    const [epochResponse, healthResponse] = await Promise.all([
                        fetch('/api/epoch'),
                        fetch('/api/health')
                    ]);

                    const epochData = await epochResponse.json();
                    const healthData = await healthResponse.json();

                    document.getElementById('currentEpoch').textContent = epochData.current_epoch || '-';
                    document.getElementById('activeMinerCount').textContent = miners.length;
                    document.getElementById('totalBlocks').textContent = healthData.total_blocks || '-';
                    document.getElementById('hashRate').textContent = (healthData.hash_rate || '-') + ' H/s';
                } catch (error) {
                    console.error('Error fetching stats:', error);
                }
            }

            async function fetchHallOfRust() {
                try {
                    const response = await fetch('/api/hall-of-rust');
                    const data = await response.json();
                    renderHallOfRust(data.hall || []);
                } catch (error) {
                    console.error('Error fetching hall of rust:', error);
                    document.getElementById('hallOfRust').innerHTML = '<p style="color: #f44336;">Failed to load hall of rust</p>';
                }
            }

            function renderHallOfRust(hall) {
                const hallDiv = document.getElementById('hallOfRust');
                if (hall.length === 0) {
                    hallDiv.innerHTML = '<p>No hall of rust entries yet.</p>';
                    return;
                }

                let html = '<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 15px;">';
                hall.forEach((entry, index) => {
                    html += `
                        <div style="background: #2a2a2a; padding: 15px; border-radius: 8px; border-left: 4px solid #ff6b35;">
                            <div style="display: flex; justify-content: between; align-items: center; margin-bottom: 10px;">
                                <span style="font-weight: bold; color: #ff6b35;">#${index + 1}</span>
                                <span style="color: #4CAF50; font-size: 1.2em; font-weight: bold;">${entry.score || 0} RTC</span>
                            </div>
                            <div style="margin-bottom: 5px;"><strong>Miner:</strong> ${entry.miner_id || 'Unknown'}</div>
                            <div style="margin-bottom: 5px;"><strong>Architecture:</strong> ${getArchBadge(entry.architecture || 'unknown')}</div>
                            <div><strong>Achievement:</strong> ${entry.achievement || 'Mining Excellence'}</div>
                        </div>
                    `;
                });
                html += '</div>';
                hallDiv.innerHTML = html;
            }

            function renderMinersTable() {
                const tbody = document.getElementById('minersTableBody');
                if (miners.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="6" style="text-align: center;">No miners found</td></tr>';
                    return;
                }

                let html = '';
                miners.forEach(miner => {
                    const lastSeen = new Date(miner.last_attestation || 0);
                    const now = new Date();
                    const minutesAgo = Math.floor((now - lastSeen) / 60000);
                    const isOnline = minutesAgo < 5;

                    html += `
                        <tr>
                            <td>${miner.miner_id || 'Unknown'}</td>
                            <td>${getArchBadge(miner.architecture || 'unknown')}</td>
                            <td class="multiplier-high">${miner.antiquity_multiplier || '1.0'}x</td>
                            <td>${minutesAgo < 1 ? 'Just now' : minutesAgo + 'm ago'}</td>
                            <td class="${isOnline ? 'status-online' : 'status-offline'}">${isOnline ? 'ONLINE' : 'OFFLINE'}</td>
                            <td>${miner.blocks_mined || 0}</td>
                        </tr>
                    `;
                });
                tbody.innerHTML = html;
            }

            function getArchBadge(arch) {
                const archMap = {
                    'G4': { class: 'arch-g4', text: 'PowerPC G4' },
                    'G5': { class: 'arch-g5', text: 'PowerPC G5' },
                    'POWER8': { class: 'arch-power8', text: 'POWER8' },
                    'Apple Silicon': { class: 'arch-apple', text: 'Apple Silicon' },
                    'Modern': { class: 'arch-modern', text: 'Modern' },
                    'unknown': { class: 'arch-modern', text: 'Unknown' }
                };
                const archInfo = archMap[arch] || archMap['unknown'];
                return `<span class="arch-badge ${archInfo.class}">${archInfo.text}</span>`;
            }

            function sortTable(column) {
                if (sortColumn === column) {
                    sortDirection *= -1;
                } else {
                    sortColumn = column;
                    sortDirection = 1;
                }

                miners.sort((a, b) => {
                    let aVal, bVal;
                    switch (column) {
                        case 0: aVal = a.miner_id || ''; bVal = b.miner_id || ''; break;
                        case 1: aVal = a.architecture || ''; bVal = b.architecture || ''; break;
                        case 2: aVal = parseFloat(a.antiquity_multiplier || 1); bVal = parseFloat(b.antiquity_multiplier || 1); break;
                        case 3: aVal = new Date(a.last_attestation || 0).getTime(); bVal = new Date(b.last_attestation || 0).getTime(); break;
                        case 4:
                            const aOnline = (new Date() - new Date(a.last_attestation || 0)) / 60000 < 5;
                            const bOnline = (new Date() - new Date(b.last_attestation || 0)) / 60000 < 5;
                            aVal = aOnline ? 1 : 0; bVal = bOnline ? 1 : 0; break;
                        case 5: aVal = parseInt(a.blocks_mined || 0); bVal = parseInt(b.blocks_mined || 0); break;
                        default: return 0;
                    }

                    if (aVal < bVal) return -1 * sortDirection;
                    if (aVal > bVal) return 1 * sortDirection;
                    return 0;
                });

                renderMinersTable();
            }

            async function lookupBalance() {
                const address = document.getElementById('walletAddress').value.trim();
                const resultDiv = document.getElementById('balanceResult');

                if (!address) {
                    resultDiv.innerHTML = '<span style="color: #f44336;">Please enter a wallet address</span>';
                    return;
                }

                resultDiv.innerHTML = 'Looking up balance...';

                try {
                    const response = await fetch(`/api/wallet-balance?address=${encodeURIComponent(address)}`);
                    const data = await response.json();

                    if (data.success) {
                        resultDiv.innerHTML = `<strong>Balance:</strong> <span style="color: #4CAF50; font-size: 1.3em;">${data.balance} RTC</span>`;
                    } else {
                        resultDiv.innerHTML = `<span style="color: #f44336;">${data.error || 'Wallet not found'}</span>`;
                    }
                } catch (error) {
                    console.error('Error looking up balance:', error);
                    resultDiv.innerHTML = '<span style="color: #f44336;">Error looking up balance</span>';
                }
            }

            async function refreshData() {
                await Promise.all([fetchMiners(), fetchStats(), fetchHallOfRust()]);
            }

            // Auto-refresh every 30 seconds
            setInterval(refreshData, 30000);

            // Initial load
            refreshData();
        </script>
    </body>
    </html>
    """
    return render_template_string(html_template)

@app.route('/api/wallet-balance')
def wallet_balance_api():
    """Get wallet balance for a given address"""
    address = request.args.get('address')
    if not address:
        return jsonify({'success': False, 'error': 'No address provided'})

    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT balance FROM wallets
                WHERE address = ?
                LIMIT 1
            """, (address,))

            result = cursor.fetchone()
            if result:
                return jsonify({
                    'success': True,
                    'balance': float(result['balance']),
                    'address': address
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Wallet not found',
                    'address': address
                })

    except Exception as e:
        return jsonify({'success': False, 'error': f'Database error: {str(e)}'})

@app.route('/api/hall-of-rust')
def hall_of_rust_api():
    """Get hall of rust leaderboard"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    m.miner_id,
                    m.architecture,
                    COUNT(b.id) as blocks_mined,
                    AVG(m.antiquity_multiplier) as avg_multiplier,
                    (COUNT(b.id) * AVG(m.antiquity_multiplier) * 10) as score
                FROM miners m
                LEFT JOIN blocks b ON b.miner_id = m.miner_id
                WHERE m.last_attestation > ?
                GROUP BY m.miner_id
                HAVING blocks_mined > 0
                ORDER BY score DESC
                LIMIT 10
            """, (datetime.now() - timedelta(days=7),))

            hall_entries = []
            for row in cursor.fetchall():
                hall_entries.append({
                    'miner_id': row['miner_id'],
                    'architecture': row['architecture'],
                    'blocks_mined': row['blocks_mined'],
                    'avg_multiplier': round(row['avg_multiplier'] or 1.0, 2),
                    'score': round(row['score'] or 0, 1),
                    'achievement': f'Mined {row["blocks_mined"]} blocks this week'
                })

            return jsonify({'success': True, 'hall': hall_entries})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e), 'hall': []})

@app.route('/api/network-stats')
def network_stats_api():
    """Enhanced network statistics"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Get various network metrics
            cursor.execute("SELECT COUNT(*) as total_miners FROM miners")
            total_miners = cursor.fetchone()['total_miners']

            cursor.execute("""
                SELECT COUNT(*) as active_miners
                FROM miners
                WHERE last_attestation > datetime('now', '-5 minutes')
            """)
            active_miners = cursor.fetchone()['active_miners']

            cursor.execute("SELECT COUNT(*) as total_blocks FROM blocks")
            total_blocks = cursor.fetchone()['total_blocks']

            cursor.execute("""
                SELECT AVG(difficulty) as avg_difficulty
                FROM blocks
                WHERE timestamp > datetime('now', '-1 hour')
            """)
            avg_difficulty = cursor.fetchone()['avg_difficulty'] or 0

            # Architecture distribution
            cursor.execute("""
                SELECT architecture, COUNT(*) as count
                FROM miners
                GROUP BY architecture
                ORDER BY count DESC
            """)
            arch_distribution = {row['architecture']: row['count'] for row in cursor.fetchall()}

            return jsonify({
                'success': True,
                'stats': {
                    'total_miners': total_miners,
                    'active_miners': active_miners,
                    'total_blocks': total_blocks,
                    'avg_difficulty': round(avg_difficulty, 2),
                    'hash_rate': round(avg_difficulty * 1000, 0),
                    'architecture_distribution': arch_distribution
                }
            })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5556, debug=True)
