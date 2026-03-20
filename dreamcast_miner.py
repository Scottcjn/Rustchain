// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import os
import sys
import json
import time
import hashlib
import sqlite3
import socket
import struct
import platform
import subprocess
from threading import Thread, Lock
from flask import Flask, request, render_template_string

DB_PATH = 'rustchain.db'
DREAMCAST_MULTIPLIER = 3.0
SH4_CACHE_SIZE = 16384

app = Flask(__name__)
mining_active = False
mining_lock = Lock()
stats = {
    'blocks_mined': 0,
    'total_hashes': 0,
    'sh4_detected': False,
    'tmu_available': False,
    'cache_timing': 0.0,
    'hardware_score': 0
}

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS blocks (
            id INTEGER PRIMARY KEY,
            hash TEXT UNIQUE,
            prev_hash TEXT,
            timestamp INTEGER,
            nonce INTEGER,
            difficulty INTEGER,
            miner_id TEXT,
            sh4_proof TEXT
        )''')
        conn.execute('''CREATE TABLE IF NOT EXISTS mining_stats (
            id INTEGER PRIMARY KEY,
            timestamp INTEGER,
            hashrate REAL,
            difficulty INTEGER,
            sh4_score INTEGER
        )''')

def detect_sh4():
    try:
        with open('/proc/cpuinfo', 'r') as f:
            cpu_info = f.read().lower()

        if 'sh4' in cpu_info or 'sh7750' in cpu_info:
            stats['sh4_detected'] = True
            return True

        arch = platform.machine().lower()
        if 'sh4' in arch or 'superh' in arch:
            stats['sh4_detected'] = True
            return True

    except:
        pass

    return False

def check_tmu_timer():
    try:
        if os.path.exists('/proc/driver/sh4_tmu'):
            stats['tmu_available'] = True
            return True

        result = subprocess.run(['dmesg', '|', 'grep', '-i', 'tmu'],
                              shell=True, capture_output=True, text=True)
        if 'tmu' in result.stdout.lower():
            stats['tmu_available'] = True
            return True

    except:
        pass

    return False

def measure_cache_timing():
    try:
        data = bytearray(SH4_CACHE_SIZE * 2)

        start = time.perf_counter()
        for i in range(0, len(data), 64):
            data[i] = (data[i] + 1) % 256
        end = time.perf_counter()

        cache_time = end - start
        stats['cache_timing'] = cache_time

        if cache_time < 0.001:
            return 100
        elif cache_time < 0.005:
            return 75
        else:
            return 25

    except:
        return 0

def generate_sh4_proof():
    proof_data = {
        'arch': platform.machine(),
        'sh4_detected': stats['sh4_detected'],
        'tmu_timer': stats['tmu_available'],
        'cache_timing': stats['cache_timing'],
        'timestamp': int(time.time())
    }

    try:
        with open('/proc/meminfo', 'r') as f:
            meminfo = f.read()
        if 'MemTotal:        16384 kB' in meminfo:
            proof_data['dreamcast_ram'] = True
    except:
        pass

    proof_str = json.dumps(proof_data, sort_keys=True)
    return hashlib.sha256(proof_str.encode()).hexdigest()

def calculate_hardware_score():
    score = 0

    if stats['sh4_detected']:
        score += 50

    if stats['tmu_available']:
        score += 25

    cache_score = measure_cache_timing()
    score += cache_score
    stats['hardware_score'] = score

    return score

def mine_block(prev_hash, difficulty):
    nonce = 0
    target = "0" * difficulty
    miner_id = f"dreamcast_{int(time.time())}"

    while mining_active:
        timestamp = int(time.time())
        block_data = f"{prev_hash}{timestamp}{nonce}{miner_id}"
        block_hash = hashlib.sha256(block_data.encode()).hexdigest()

        if block_hash.startswith(target):
            sh4_proof = generate_sh4_proof()

            with sqlite3.connect(DB_PATH) as conn:
                try:
                    conn.execute('''INSERT INTO blocks
                                  (hash, prev_hash, timestamp, nonce, difficulty, miner_id, sh4_proof)
                                  VALUES (?, ?, ?, ?, ?, ?, ?)''',
                               (block_hash, prev_hash, timestamp, nonce, difficulty, miner_id, sh4_proof))

                    with mining_lock:
                        stats['blocks_mined'] += 1

                    print(f"Block mined: {block_hash[:16]}... (SH4 multiplier: {DREAMCAST_MULTIPLIER}x)")
                    return block_hash

                except sqlite3.IntegrityError:
                    pass

        nonce += 1
        with mining_lock:
            stats['total_hashes'] += 1

        if nonce % 1000 == 0:
            time.sleep(0.001)

    return None

def mining_thread():
    global mining_active

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute('SELECT hash FROM blocks ORDER BY id DESC LIMIT 1')
        result = cursor.fetchone()
        prev_hash = result[0] if result else "0" * 64

    difficulty = 4

    while mining_active:
        mine_block(prev_hash, difficulty)

        if stats['blocks_mined'] % 10 == 0:
            difficulty += 1

def start_mining():
    global mining_active

    if mining_active:
        return False

    print("Initializing Dreamcast SH4 miner...")

    sh4_found = detect_sh4()
    tmu_found = check_tmu_timer()
    hw_score = calculate_hardware_score()

    print(f"SH4 detected: {sh4_found}")
    print(f"TMU timer: {tmu_found}")
    print(f"Hardware score: {hw_score}/100")
    print(f"Antiquity multiplier: {DREAMCAST_MULTIPLIER}x")

    mining_active = True
    Thread(target=mining_thread, daemon=True).start()

    return True

def stop_mining():
    global mining_active
    mining_active = False

@app.route('/')
def dashboard():
    html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Dreamcast RustChain Miner</title>
        <meta http-equiv="refresh" content="5">
        <style>
            body { font-family: monospace; background: #001122; color: #00ff88; padding: 20px; }
            .header { color: #ff6600; font-size: 24px; margin-bottom: 20px; }
            .stats { background: #112233; padding: 15px; margin: 10px 0; border-radius: 5px; }
            .mining { color: #ffff00; }
            .sh4 { color: #ff3366; font-weight: bold; }
        </style>
    </head>
    <body>
        <div class="header">🎮 DREAMCAST RUSTCHAIN MINER 🎮</div>

        <div class="stats">
            <div class="sh4">SH4 STATUS</div>
            Architecture: {{ 'SH4 SuperH' if stats.sh4_detected else 'Unknown' }}<br>
            TMU Timer: {{ 'Available' if stats.tmu_available else 'Not Found' }}<br>
            Cache Timing: {{ "%.6f"|format(stats.cache_timing) }}s<br>
            Hardware Score: {{ stats.hardware_score }}/100<br>
            Antiquity Multiplier: {{ multiplier }}x
        </div>

        <div class="stats">
            <div class="mining">MINING STATUS</div>
            Active: {{ 'YES' if mining_active else 'NO' }}<br>
            Blocks Mined: {{ stats.blocks_mined }}<br>
            Total Hashes: {{ "{:,}"|format(stats.total_hashes) }}<br>
            Hashrate: {{ "{:.1f}"|format(stats.total_hashes / 60) }} H/s
        </div>

        <div class="stats">
            <a href="/start" style="color: #00ff88;">Start Mining</a> |
            <a href="/stop" style="color: #ff6600;">Stop Mining</a>
        </div>
    </body>
    </html>
    '''

    return render_template_string(html,
                                stats=stats,
                                mining_active=mining_active,
                                multiplier=DREAMCAST_MULTIPLIER)

@app.route('/start')
def start():
    if start_mining():
        return "Mining started on SH4 architecture!"
    return "Mining already active!"

@app.route('/stop')
def stop():
    stop_mining()
    return "Mining stopped!"

@app.route('/api/stats')
def api_stats():
    return json.dumps({
        'mining_active': mining_active,
        'stats': stats,
        'multiplier': DREAMCAST_MULTIPLIER,
        'arch': 'sh4' if stats['sh4_detected'] else 'unknown'
    })

def main():
    print("Dreamcast RustChain Miner v1.0")
    print("SH4 Architecture - 3.0x Antiquity Multiplier")
    print("=" * 50)

    init_db()

    detect_sh4()
    check_tmu_timer()
    calculate_hardware_score()

    if len(sys.argv) > 1 and sys.argv[1] == 'mine':
        start_mining()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            stop_mining()
            print("\nMining stopped.")
    else:
        print("Starting web interface on port 5000...")
        app.run(host='0.0.0.0', port=5000, debug=False)

if __name__ == '__main__':
    main()
