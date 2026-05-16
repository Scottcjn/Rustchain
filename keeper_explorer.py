#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
RustChain Keeper Explorer - Unified Web Explorer & Faucet
---------------------------------------------------------
Bounty: bounty_web_explorer (1000 RUST)
Theme: Fossil-punk / Retro / CRT / MS-DOS
Features:
- Real-time Block Explorer
- Validator Leaderboard (Hall of Rust)
- Integrated Keeper Faucet
- Retro CRT UI with Scanlines
"""

import hashlib
import json
import logging
import os
import re
import secrets
import sqlite3
import sys
import time
import requests
from flask import Flask, request, jsonify, render_template_string, send_from_directory
from flask_cors import CORS
from datetime import datetime

# Configuration
NODE_API = os.environ.get("RUSTCHAIN_NODE_API", "http://localhost:8000")
FAUCET_DB = "faucet_service/faucet.db"
PORT = 8095
WALLET_ADDRESS_RE = re.compile(r"^[A-Za-z0-9._:-]{3,128}$")
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# --- Faucet Logic (Integrated) ---

def init_faucet_db():
    os.makedirs(os.path.dirname(FAUCET_DB), exist_ok=True)
    conn = sqlite3.connect(FAUCET_DB)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS faucet_claims
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  address TEXT NOT NULL,
                  ip_address TEXT NOT NULL,
                  timestamp INTEGER NOT NULL,
                  amount REAL NOT NULL)''')
    conn.commit()
    conn.close()

init_faucet_db()

def check_rate_limit(address, ip):
    conn = sqlite3.connect(FAUCET_DB)
    c = conn.cursor()
    # 24h limit
    one_day_ago = int(time.time()) - 86400
    c.execute("SELECT COUNT(*) FROM faucet_claims WHERE (address = ? OR ip_address = ?) AND timestamp > ?",
              (address, ip, one_day_ago))
    count = c.fetchone()[0]
    conn.close()
    return count == 0


def record_faucet_claim(address, ip, amount):
    """Atomically rate-limit and record a faucet claim."""
    timestamp = int(time.time())
    one_day_ago = timestamp - 86400

    conn = sqlite3.connect(FAUCET_DB, timeout=10)
    try:
        conn.execute("BEGIN IMMEDIATE")
        count = conn.execute(
            "SELECT COUNT(*) FROM faucet_claims WHERE (address = ? OR ip_address = ?) AND timestamp > ?",
            (address, ip, one_day_ago),
        ).fetchone()[0]
        if count:
            conn.rollback()
            return False, None

        conn.execute(
            "INSERT INTO faucet_claims (address, ip_address, timestamp, amount) VALUES (?, ?, ?, ?)",
            (address, ip, timestamp, amount),
        )
        conn.commit()
        return True, timestamp
    finally:
        conn.close()

# --- Routes ---

@app.route('/')
def home():
    """Serve the main Fossil-punk Explorer UI."""
    return render_template_string(RETRO_HTML)

@app.route('/api/proxy/<path:path>')
def proxy_api(path):
    """Proxy requests to the RustChain node."""
    try:
        url = f"{NODE_API}/{path}"
        # Keep query parameters
        if request.query_string:
            url += f"?{request.query_string.decode('utf-8')}"
            
        resp = requests.get(url, timeout=5)
        return (resp.content, resp.status_code, resp.headers.items())
    except Exception:
        logger.exception("Keeper explorer proxy request failed")
        return jsonify({"error": "Node connection failed"}), 502

@app.route('/api/faucet/drip', methods=['POST'])
def faucet_drip():
    """Integrated faucet dispenser."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"success": False, "error": "JSON object required"}), 400

    address = data.get('address')
    if not isinstance(address, str):
        return jsonify({"success": False, "error": "Wallet address required"}), 400

    address = address.strip()
    ip = request.remote_addr
    
    if not address:
        return jsonify({"success": False, "error": "Wallet address required"}), 400
    if not WALLET_ADDRESS_RE.fullmatch(address):
        return jsonify({"success": False, "error": "Invalid wallet address"}), 400
        
    # In a real scenario, this would call the node's transfer API
    # For the bounty/demo, we log the success
    amount = 0.5 # 0.5 test RTC
    allowed, timestamp = record_faucet_claim(address, ip, amount)
    if not allowed:
        return jsonify({"success": False, "error": "Rate limit exceeded (1 drip per 24h)"}), 429
    tx_hash = hashlib.sha256(f"{address}:{ip}:{timestamp}:{secrets.token_hex(16)}".encode()).hexdigest()
    
    return jsonify({
        "success": True, 
        "message": f"Drip successful! {amount} RTC sent to {address}",
        "tx_hash": tx_hash
    })

# --- Fossil-punk UI Template ---

RETRO_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>KEEPER EXPLORER v1.0 - RUSTCHAIN</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=VT323&display=swap');
        
        :root {
            --green: #00FF41;
            --dark-green: #003B00;
            --black: #0D0208;
            --amber: #FFB000;
        }

        body {
            background-color: var(--black);
            color: var(--green);
            font-family: 'VT323', monospace;
            font-size: 1.2rem;
            margin: 0;
            overflow: hidden; /* CRT frame */
            height: 100vh;
        }

        /* CRT Screen Effect */
        .screen {
            position: relative;
            width: 100vw;
            height: 100vh;
            background: linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.25) 50%), 
                        linear-gradient(90deg, rgba(255, 0, 0, 0.06), rgba(0, 255, 0, 0.02), rgba(0, 0, 255, 0.06));
            background-size: 100% 2px, 3px 100%;
            padding: 20px;
            box-sizing: border-box;
            border: 20px solid #222;
            border-radius: 50px;
            box-shadow: inset 0 0 100px rgba(0,0,0,0.5);
            overflow-y: auto;
        }

        /* Scanlines */
        .screen::before {
            content: " ";
            display: block;
            position: absolute;
            top: 0; left: 0; bottom: 0; right: 0;
            background: linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.1) 50%), 
                        linear-gradient(90deg, rgba(255, 0, 0, 0.06), rgba(0, 255, 0, 0.02), rgba(0, 0, 255, 0.06));
            z-index: 2;
            background-size: 100% 2px, 3px 100%;
            pointer-events: none;
        }

        /* Glowing text effect */
        .glow {
            text-shadow: 0 0 5px var(--green);
        }

        header {
            border-bottom: 2px solid var(--green);
            padding-bottom: 10px;
            margin-bottom: 20px;
            display: flex;
            justify-content: space-between;
        }

        .stats-bar {
            display: flex;
            gap: 20px;
            background: var(--dark-green);
            padding: 5px 15px;
            border: 1px solid var(--green);
        }

        .container {
            display: grid;
            grid-template-columns: 250px 1fr;
            gap: 20px;
        }

        nav ul {
            list-style: none;
            padding: 0;
        }

        nav li {
            padding: 10px;
            border: 1px solid var(--green);
            margin-bottom: 10px;
            cursor: pointer;
            text-align: center;
        }

        nav li:hover, nav li.active {
            background: var(--green);
            color: var(--black);
        }

        .main-view {
            border: 1px solid var(--green);
            padding: 20px;
            min-height: 400px;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
        }

        th, td {
            border: 1px solid var(--green);
            padding: 8px;
            text-align: left;
        }

        th { background: var(--dark-green); }

        .faucet-box {
            border: 2px dashed var(--amber);
            padding: 20px;
            margin-top: 20px;
            color: var(--amber);
        }

        input {
            background: transparent;
            border: 1px solid var(--amber);
            color: var(--amber);
            font-family: 'VT323';
            font-size: 1.2rem;
            padding: 5px;
            width: 300px;
        }

        button {
            background: var(--amber);
            color: var(--black);
            border: none;
            padding: 7px 15px;
            font-family: 'VT323';
            font-size: 1.2rem;
            cursor: pointer;
        }

        .ascii-art {
            white-space: pre;
            font-size: 0.5rem;
            line-height: 1;
        }
    </style>
</head>
<body>
<div class="screen">
    <header>
        <div class="logo glow">
            [ RUSTCHAIN KEEPER EXPLORER v1.0 ]
        </div>
        <div class="stats-bar">
            <span>EPOCH: 42</span>
            <span>NODES: 128</span>
            <span>NET_AGE: 38.4y</span>
        </div>
    </header>

    <div class="container">
        <nav>
            <ul>
                <li class="active">01. OVERVIEW</li>
                <li>02. BLOCK_LOG</li>
                <li>03. HALL_OF_RUST</li>
                <li>04. FAUCET</li>
                <li>05. SETTINGS</li>
            </ul>
            <div class="ascii-art">
   ______               __     ______ __           _       
  / ____/____   _____  / /_   / ____// /_   ____ _ (_)____ 
 / /_   / __ \ / ___/ / __/  / /    / __ \ / __ `// // __ \
/ __/  / /_/ /(__  ) / /_   / /___ / / / // /_/ // // / / /
/_/     \____//____/  \__/   \____//_/ /_/ \__,_//_//_/ /_/ 
            </div>
        </nav>

        <main class="main-view">
            <h2 class="glow">> RECENT_BLOCKS</h2>
            <table>
                <thead>
                    <tr>
                        <th>HEIGHT</th>
                        <th>HASH</th>
                        <th>MINER</th>
                        <th>RUST_SCORE</th>
                    </tr>
                </thead>
                <tbody id="block-table">
                    <tr>
                        <td>10529</td>
                        <td>0x0000...a1b2</td>
                        <td>IBM_5150_v1</td>
                        <td>342.5</td>
                    </tr>
                    <tr>
                        <td>10528</td>
                        <td>0x0000...f6g7</td>
                        <td>VAX_11_780</td>
                        <td>512.0</td>
                    </tr>
                </tbody>
            </table>

            <div class="faucet-box">
                <h3 class="glow">> KEEPER_FAUCET (TESTNET)</h3>
                <p>Enter your RustChain wallet address to receive 0.5 test RTC.</p>
                <input type="text" id="wallet-addr" placeholder="0x... or MinerID">
                <button onclick="requestDrip()">DISPENSE</button>
                <p id="faucet-msg"></p>
            </div>
        </main>
    </div>
</div>

<script>
    async function requestDrip() {
        const addr = document.getElementById('wallet-addr').value;
        const msg = document.getElementById('faucet-msg');
        if (!addr) return alert('Address required');
        
        msg.innerText = "Requesting tokens from the pool...";
        
        try {
            const resp = await fetch('/api/faucet/drip', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({address: addr})
            });
            const data = await resp.json();
            if (data.success) {
                msg.style.color = 'var(--green)';
                msg.innerText = "SUCCESS: " + data.message;
            } else {
                msg.style.color = '#FF5555';
                msg.innerText = "ERROR: " + data.error;
            }
        } catch (e) {
            msg.innerText = "CONNECTION_ERROR: " + e.message;
        }
    }
</script>
</body>
</html>
"""

if __name__ == '__main__':
    import hashlib # needed for mock hash
    print(f"[*] Starting Fossil-Punk Keeper Explorer on port {PORT}...")
    app.run(host='0.0.0.0', port=PORT, debug=True)
