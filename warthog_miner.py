// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import json
import requests
import psutil
import sqlite3
import time
import logging
from datetime import datetime, timedelta
from flask import Flask, render_template_string, jsonify
import threading

DB_PATH = "rustchain.db"
WARTHOG_NODES = ["http://localhost:3000", "http://localhost:3001"]
WARTHOG_PROCESSES = ["wart-miner", "warthog-miner", "janushash"]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WarthogMiner:
    def __init__(self):
        self.last_check = None
        self.mining_active = False
        self.node_verified = False
        self.pool_verified = False
        self.current_height = 0
        self.init_db()

    def init_db(self):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS warthog_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    mining_active INTEGER,
                    node_verified INTEGER,
                    pool_verified INTEGER,
                    chain_height INTEGER,
                    bonus_multiplier REAL
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS warthog_processes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    process_name TEXT,
                    pid INTEGER,
                    start_time TEXT,
                    last_seen TEXT
                )
            ''')

    def detect_warthog_processes(self):
        active_processes = []
        for proc in psutil.process_iter(['pid', 'name', 'create_time']):
            try:
                proc_name = proc.info['name'].lower()
                if any(wart_proc in proc_name for wart_proc in WARTHOG_PROCESSES):
                    start_time = datetime.fromtimestamp(proc.info['create_time'])
                    active_processes.append({
                        'name': proc.info['name'],
                        'pid': proc.info['pid'],
                        'start_time': start_time.isoformat()
                    })

                    with sqlite3.connect(DB_PATH) as conn:
                        conn.execute('''
                            INSERT OR REPLACE INTO warthog_processes
                            (process_name, pid, start_time, last_seen)
                            VALUES (?, ?, ?, ?)
                        ''', (proc.info['name'], proc.info['pid'],
                             start_time.isoformat(), datetime.now().isoformat()))

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        self.mining_active = len(active_processes) > 0
        return active_processes

    def verify_warthog_node(self):
        for node_url in WARTHOG_NODES:
            try:
                response = requests.get(f"{node_url}/chain/head", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    self.current_height = data.get('height', 0)
                    self.node_verified = True
                    logger.info(f"Warthog node verified at {node_url}, height: {self.current_height}")
                    return True
            except requests.RequestException:
                continue

        self.node_verified = False
        return False

    def verify_pool_account(self, pool_address=None, worker_name=None):
        # WoolyPooly API check
        if pool_address and worker_name:
            try:
                woolypooly_url = f"https://api.woolypooly.com/api/wart-pplns/accounts/{pool_address}"
                response = requests.get(woolypooly_url, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    workers = data.get('workers', {})
                    if worker_name in workers:
                        self.pool_verified = True
                        logger.info(f"Pool account verified: {pool_address}/{worker_name}")
                        return True
            except requests.RequestException:
                pass

        # Alternative pool check could go here
        self.pool_verified = False
        return False

    def calculate_bonus_multiplier(self):
        multiplier = 1.0
        if self.node_verified:
            multiplier *= 1.5
        if self.pool_verified:
            multiplier *= 1.3
        return multiplier

    def run_rip_poa_check(self):
        """RIP-PoA fingerprinting - lightweight 5-second check"""
        start_time = time.time()

        processes = self.detect_warthog_processes()
        node_ok = self.verify_warthog_node()
        bonus_mult = self.calculate_bonus_multiplier()

        # Store stats
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''
                INSERT INTO warthog_stats
                (timestamp, mining_active, node_verified, pool_verified,
                 chain_height, bonus_multiplier)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (datetime.now().isoformat(),
                  int(self.mining_active), int(self.node_verified),
                  int(self.pool_verified), self.current_height, bonus_mult))

        check_duration = time.time() - start_time
        logger.info(f"RIP-PoA check completed in {check_duration:.2f}s - "
                   f"Mining: {self.mining_active}, Node: {node_ok}, "
                   f"Bonus: {bonus_mult:.2f}x")

        self.last_check = datetime.now()
        return {
            'processes': processes,
            'node_verified': node_ok,
            'pool_verified': self.pool_verified,
            'bonus_multiplier': bonus_mult,
            'check_duration': check_duration
        }

    def background_monitor(self):
        """Run checks every 10 minutes"""
        while True:
            try:
                self.run_rip_poa_check()
                time.sleep(600)  # 10 minutes
            except Exception as e:
                logger.error(f"Background monitor error: {e}")
                time.sleep(60)

app = Flask(__name__)
warthog = WarthogMiner()

@app.route('/warthog')
def warthog_dashboard():
    template = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Warthog Dual-Mining Dashboard</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            .status { padding: 10px; margin: 10px 0; border-radius: 5px; }
            .active { background-color: #d4edda; border: 1px solid #c3e6cb; }
            .inactive { background-color: #f8d7da; border: 1px solid #f5c6cb; }
            .bonus { background-color: #d1ecf1; border: 1px solid #bee5eb; }
            table { border-collapse: collapse; width: 100%; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
            th { background-color: #f2f2f2; }
        </style>
    </head>
    <body>
        <h1>Warthog (Janushash) Dual-Mining</h1>

        <div class="status {{ 'active' if mining_active else 'inactive' }}">
            <h3>Mining Status: {{ 'ACTIVE' if mining_active else 'INACTIVE' }}</h3>
            <p>Processes detected: {{ process_count }}</p>
            <p>Last check: {{ last_check or 'Never' }}</p>
        </div>

        <div class="status {{ 'active' if node_verified else 'inactive' }}">
            <h3>Node Verification: {{ 'VERIFIED' if node_verified else 'FAILED' }}</h3>
            <p>Current height: {{ current_height }}</p>
            <p>Bonus: {{ '1.5x' if node_verified else '1.0x' }}</p>
        </div>

        <div class="status {{ 'active' if pool_verified else 'inactive' }}">
            <h3>Pool Verification: {{ 'VERIFIED' if pool_verified else 'NOT CONFIGURED' }}</h3>
            <p>Bonus: {{ '1.3x' if pool_verified else '1.0x' }}</p>
        </div>

        <div class="bonus">
            <h3>Total Bonus Multiplier: {{ bonus_multiplier }}x</h3>
        </div>

        <h3>Recent Activity</h3>
        <table>
            <tr>
                <th>Timestamp</th>
                <th>Mining</th>
                <th>Node OK</th>
                <th>Pool OK</th>
                <th>Height</th>
                <th>Bonus</th>
            </tr>
            {% for stat in recent_stats %}
            <tr>
                <td>{{ stat[0] }}</td>
                <td>{{ '✓' if stat[1] else '✗' }}</td>
                <td>{{ '✓' if stat[2] else '✗' }}</td>
                <td>{{ '✓' if stat[3] else '✗' }}</td>
                <td>{{ stat[4] }}</td>
                <td>{{ stat[5] }}x</td>
            </tr>
            {% endfor %}
        </table>

        <p><a href="/warthog/check">Force Check</a> | <a href="/warthog/api">JSON API</a></p>
    </body>
    </html>
    '''

    # Get recent stats
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute('''
            SELECT timestamp, mining_active, node_verified, pool_verified,
                   chain_height, bonus_multiplier
            FROM warthog_stats
            ORDER BY timestamp DESC LIMIT 10
        ''')
        recent_stats = cursor.fetchall()

    processes = warthog.detect_warthog_processes()

    return render_template_string(template,
        mining_active=warthog.mining_active,
        node_verified=warthog.node_verified,
        pool_verified=warthog.pool_verified,
        current_height=warthog.current_height,
        bonus_multiplier=warthog.calculate_bonus_multiplier(),
        process_count=len(processes),
        last_check=warthog.last_check.strftime('%Y-%m-%d %H:%M:%S') if warthog.last_check else None,
        recent_stats=recent_stats
    )

@app.route('/warthog/check')
def force_check():
    result = warthog.run_rip_poa_check()
    return jsonify(result)

@app.route('/warthog/api')
def warthog_api():
    return jsonify({
        'mining_active': warthog.mining_active,
        'node_verified': warthog.node_verified,
        'pool_verified': warthog.pool_verified,
        'current_height': warthog.current_height,
        'bonus_multiplier': warthog.calculate_bonus_multiplier(),
        'last_check': warthog.last_check.isoformat() if warthog.last_check else None
    })

def start_background_monitor():
    monitor_thread = threading.Thread(target=warthog.background_monitor, daemon=True)
    monitor_thread.start()

if __name__ == '__main__':
    start_background_monitor()
    app.run(debug=True, host='0.0.0.0', port=5002)
