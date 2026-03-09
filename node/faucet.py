#!/usr/bin/env python3
"""
RustChain Testnet Faucet
-------------------------
A simple faucet service that distributes test RTC to developers.
"""
import sqlite3
import json
import time
import os
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template_string
import requests

app = Flask(__name__)

# Configuration
DB_PATH = "/root/rustchain/faucet.db"
NODE_API = os.environ.get("NODE_API", "http://localhost:8088")
FAUCET_WALLET = os.environ.get("FAUCET_WALLET", "faucet_pool")
ADMIN_KEY = os.environ.get("ADMIN_KEY", "change-me-in-production")

# Rate limits (in seconds)
RATE_LIMIT_IP = 24 * 60 * 60  # 24 hours
RATE_LIMIT_GITHUB = 24 * 60 * 60  # 24 hours

# Amounts
AMOUNT_NO_AUTH = 0.5  # RTC
AMOUNT_GITHUB = 1.0  # RTC
AMOUNT_GITHUB_OLD = 2.0  # RTC (account > 1 year)


def init_db():
    """Initialize SQLite database for tracking faucet usage."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS faucet_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wallet TEXT NOT NULL,
            github_username TEXT,
            ip_address TEXT NOT NULL,
            amount REAL NOT NULL,
            tx_hash TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS rate_limits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            identifier TEXT NOT NULL UNIQUE,
            identifier_type TEXT NOT NULL,
            last_request DATETIME NOT NULL,
            request_count INTEGER DEFAULT 1
        )
    ''')
    conn.commit()
    conn.close()


def check_rate_limit(identifier, identifier_type="ip"):
    """Check if identifier has exceeded rate limit."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('''
        SELECT last_request, request_count FROM rate_limits
        WHERE identifier = ? AND identifier_type = ?
    ''', (identifier, identifier_type))
    
    row = c.fetchone()
    conn.close()
    
    if not row:
        return True, None  # No record, allow
    
    last_request = datetime.fromisoformat(row[0])
    elapsed = (datetime.now() - last_request).total_seconds()
    
    if elapsed < RATE_LIMIT_IP:
        next_available = last_request + timedelta(seconds=RATE_LIMIT_IP)
        return False, next_available
    
    return True, None


def update_rate_limit(identifier, identifier_type="ip"):
    """Update rate limit record."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('''
        INSERT INTO rate_limits (identifier, identifier_type, last_request, request_count)
        VALUES (?, ?, datetime('now'), 1)
        ON CONFLICT(identifier) DO UPDATE SET
            last_request = datetime('now'),
            request_count = request_count + 1
    ''', (identifier, identifier_type))
    
    conn.commit()
    conn.close()


def get_github_account_age(username):
    """Check GitHub account age via API."""
    try:
        resp = requests.get(f"https://api.github.com/users/{username}", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            created_at = datetime.strptime(data['created_at'], '%Y-%m-%dT%H:%M:%SZ')
            age_days = (datetime.now() - created_at).days
            return age_days
    except:
        pass
    return None


def transfer_to_wallet(to_wallet, amount):
    """Transfer RTC via node API."""
    try:
        # This would call the actual RustChain transfer API
        # For now, return a mock response
        payload = {
            "from_wallet": FAUCET_WALLET,
            "to_wallet": to_wallet,
            "amount": amount
        }
        # In production: resp = requests.post(f"{NODE_API}/wallet/transfer", json=payload)
        return {
            "ok": True,
            "pending_id": int(time.time()),
            "tx_hash": f"faucet_{int(time.time())}"
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


# HTML Template
FAUCET_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>RustChain Testnet Faucet</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            color: #fff;
            padding: 20px;
            min-height: 100vh;
        }
        .container { max-width: 600px; margin: 0 auto; padding-top: 50px; }
        .header {
            text-align: center;
            margin-bottom: 30px;
            padding: 30px;
            background: rgba(255,255,255,0.1);
            border-radius: 15px;
            backdrop-filter: blur(10px);
        }
        .header h1 { font-size: 2.5em; margin-bottom: 10px; }
        .header p { opacity: 0.9; font-size: 1.1em; }
        .form-card {
            background: rgba(255,255,255,0.95);
            color: #333;
            padding: 30px;
            border-radius: 15px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.3);
        }
        .form-group { margin-bottom: 20px; }
        .form-group label { 
            display: block; 
            margin-bottom: 8px; 
            font-weight: 600;
            color: #555;
        }
        .form-group input {
            width: 100%;
            padding: 12px 15px;
            border: 2px solid #ddd;
            border-radius: 8px;
            font-size: 16px;
            transition: border-color 0.3s;
        }
        .form-group input:focus {
            outline: none;
            border-color: #2a5298;
        }
        .btn {
            width: 100%;
            padding: 15px;
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 18px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s;
        }
        .btn:hover { transform: translateY(-2px); }
        .btn:disabled { opacity: 0.6; cursor: not-allowed; }
        .result {
            margin-top: 20px;
            padding: 15px;
            border-radius: 8px;
            display: none;
        }
        .result.success { 
            background: #d4edda; 
            color: #155724;
            display: block;
        }
        .result.error { 
            background: #f8d7da; 
            color: #721c24;
            display: block;
        }
        .limits {
            margin-top: 30px;
            padding: 20px;
            background: rgba(0,0,0,0.1);
            border-radius: 10px;
        }
        .limits h3 { margin-bottom: 15px; }
        .limits table { width: 100%; border-collapse: collapse; }
        .limits td { padding: 8px; border-bottom: 1px solid rgba(255,255,255,0.1); }
        .limits td:last-child { text-align: right; font-weight: 600; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 RustChain Faucet</h1>
            <p>Get free test RTC for development</p>
        </div>
        
        <div class="form-card">
            <form id="faucetForm">
                <div class="form-group">
                    <label>Your RTC Wallet Address</label>
                    <input type="text" name="wallet" required placeholder="Enter your wallet name or address">
                </div>
                <div class="form-group">
                    <label>GitHub Username (optional)</label>
                    <input type="text" name="github_username" placeholder="Enter GitHub username for higher limits">
                </div>
                <button type="submit" class="btn">Get Test RTC</button>
            </form>
            
            <div id="result" class="result"></div>
        </div>
        
        <div class="limits">
            <h3>Rate Limits</h3>
            <table>
                <tr><td>No authentication</td><td>0.5 RTC / 24h</td></tr>
                <tr><td>GitHub OAuth</td><td>1.0 RTC / 24h</td></tr>
                <tr><td>GitHub account > 1 year</td><td>2.0 RTC / 24h</td></tr>
            </table>
        </div>
    </div>
    
    <script>
        document.getElementById('faucetForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(e.target);
            const data = Object.fromEntries(formData);
            
            const btn = e.target.querySelector('button');
            btn.disabled = true;
            btn.textContent = 'Processing...';
            
            try {
                const resp = await fetch('/faucet/drip', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(data)
                });
                const result = await resp.json();
                
                const resultDiv = document.getElementById('result');
                if (result.ok) {
                    resultDiv.className = 'result success';
                    resultDiv.innerHTML = `
                        <strong>Success!</strong><br>
                        Sent: ${result.amount} RTC<br>
                        Pending ID: ${result.pending_id}<br>
                        Next available: ${result.next_available}
                    `;
                } else {
                    resultDiv.className = 'result error';
                    resultDiv.innerHTML = `<strong>Error:</strong> ${result.error}`;
                }
            } catch (err) {
                const resultDiv = document.getElementById('result');
                resultDiv.className = 'result error';
                resultDiv.innerHTML = `<strong>Error:</strong> ${err.message}`;
            }
            
            btn.disabled = false;
            btn.textContent = 'Get Test RTC';
        });
    </script>
</body>
</html>
"""


@app.route('/')
def index():
    """Serve faucet homepage."""
    return render_template_string(FAUCET_HTML)


@app.route('/faucet/drip', methods=['POST'])
def drip():
    """Process faucet drip request."""
    data = request.get_json() or {}
    wallet = data.get('wallet', '').strip()
    github_username = data.get('github_username', '').strip()
    ip_address = request.remote_addr
    
    # Validate wallet
    if not wallet:
        return jsonify({"ok": False, "error": "Wallet address required"}), 400
    
    # Check IP rate limit
    allowed, next_available = check_rate_limit(ip_address, "ip")
    if not allowed:
        return jsonify({
            "ok": False,
            "error": "Rate limit exceeded",
            "next_available": next_available.isoformat() if next_available else None
        }), 429
    
    # Determine amount based on GitHub auth
    amount = AMOUNT_NO_AUTH
    if github_username:
        age = get_github_account_age(github_username)
        if age and age > 365:
            amount = AMOUNT_GITHUB_OLD
        else:
            amount = AMOUNT_GITHUB
        
        # Check GitHub rate limit
        allowed_gh, _ = check_rate_limit(github_username, "github")
        if not allowed_gh:
            return jsonify({
                "ok": False,
                "error": "GitHub account rate limit exceeded"
            }), 429
    
    # Process transfer
    result = transfer_to_wallet(wallet, amount)
    
    if result.get("ok"):
        # Update rate limits
        update_rate_limit(ip_address, "ip")
        if github_username:
            update_rate_limit(github_username, "github")
        
        # Log the transaction
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''
            INSERT INTO faucet_logs (wallet, github_username, ip_address, amount, tx_hash)
            VALUES (?, ?, ?, ?, ?)
        ''', (wallet, github_username, ip_address, amount, result.get("tx_hash")))
        conn.commit()
        conn.close()
        
        next_time = datetime.now() + timedelta(seconds=RATE_LIMIT_IP)
        
        return jsonify({
            "ok": True,
            "amount": amount,
            "pending_id": result.get("pending_id"),
            "tx_hash": result.get("tx_hash"),
            "next_available": next_time.isoformat()
        })
    
    return jsonify({"ok": False, "error": result.get("error", "Transfer failed")}), 500


@app.route('/faucet/status/<wallet>', methods=['GET'])
def status(wallet):
    """Check if wallet has received from faucet."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        SELECT SUM(amount), COUNT(*) FROM faucet_logs WHERE wallet = ?
    ''', (wallet,))
    row = c.fetchone()
    conn.close()
    
    return jsonify({
        "wallet": wallet,
        "total_received": row[0] or 0,
        "request_count": row[1] or 0
    })


@app.route('/faucet/stats', methods=['GET'])
def stats():
    """Get faucet statistics."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('SELECT COUNT(*), SUM(amount) FROM faucet_logs')
    total = c.fetchone()
    
    c.execute('SELECT COUNT(DISTINCT wallet) FROM faucet_logs')
    unique_wallets = c.fetchone()[0]
    
    c.execute('SELECT COUNT(DISTINCT github_username) FROM faucet_logs WHERE github_username IS NOT NULL')
    github_users = c.fetchone()[0]
    
    conn.close()
    
    return jsonify({
        "total_requests": total[0] or 0,
        "total_distributed": total[1] or 0,
        "unique_wallets": unique_wallets or 0,
        "github_authenticated": github_users or 0
    })


if __name__ == '__main__':
    init_db()
    print("Starting RustChain Faucet on port 8089...")
    app.run(host='0.0.0.0', port=8089, debug=False)
