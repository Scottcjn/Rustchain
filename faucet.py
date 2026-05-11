#!/usr/bin/env python3
"""
RustChain Testnet Faucet
A simple Flask web application that dispenses test RTC tokens.

Features:
- IP-based rate limiting
- SQLite backend for tracking
- Simple HTML form for requesting tokens
"""

import sqlite3
import time
import os
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template_string
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
DATABASE = 'faucet.db'

# Rate limiting settings (per 24 hours)
MAX_DRIP_AMOUNT = 0.5  # RTC
RATE_LIMIT_HOURS = 24


def init_db():
    """Initialize the SQLite database."""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS drip_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wallet TEXT NOT NULL,
            ip_address TEXT NOT NULL,
            amount REAL NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()


def get_client_ip():
    """Get client IP address safely considering reverse proxies.
    
    SECURITY: Handled transparently by Werkzeug ProxyFix.
    """
    remote = request.remote_addr or '127.0.0.1'
    return remote
def get_last_drip_time(identifier, is_wallet=False):
    """Get the last time this IP or wallet requested a drip."""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    
    if is_wallet:
        c.execute('''
            SELECT timestamp FROM drip_requests
            WHERE wallet = ?
            ORDER BY timestamp DESC
            LIMIT 1
        ''', (identifier,))
    else:
        c.execute('''
            SELECT timestamp FROM drip_requests
            WHERE ip_address = ?
            ORDER BY timestamp DESC
            LIMIT 1
        ''', (identifier,))
        
    result = c.fetchone()
    conn.close()
    return result[0] if result else None
def can_drip(identifier, is_wallet=False):
    """Check if the IP or Wallet can request a drip (rate limiting)."""
    last_time = get_last_drip_time(identifier, is_wallet)
    if not last_time:
        return True
    
    last_drip = datetime.fromisoformat(last_time.replace('Z', '+00:00'))
    now = datetime.now(last_drip.tzinfo)
    hours_since = (now - last_drip).total_seconds() / 3600
    
    return hours_since >= RATE_LIMIT_HOURS


def get_next_available(identifier, is_wallet=False):
    """Get the next available time for this IP or wallet."""
    last_time = get_last_drip_time(identifier, is_wallet)
    if not last_time:
        return None
    
    last_drip = datetime.fromisoformat(last_time.replace('Z', '+00:00'))
    next_available = last_drip + timedelta(hours=RATE_LIMIT_HOURS)
    now = datetime.now(last_drip.tzinfo)
    
    if next_available > now:
        return next_available.isoformat()
    return None


def record_drip(wallet, ip_address, amount):
    """Record a drip request to the database."""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''
        INSERT INTO drip_requests (wallet, ip_address, amount)
        VALUES (?, ?, ?)
    ''', (wallet, ip_address, amount))
    conn.commit()
    conn.close()


# HTML Template
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>RustChain Testnet Faucet</title>
    <style>
        body {
            font-family: 'Courier New', monospace;
            max-width: 600px;
            margin: 50px auto;
            padding: 20px;
            background: #0a0a0a;
            color: #00ff00;
        }
        h1 {
            color: #00ff00;
            border-bottom: 2px solid #00ff00;
            padding-bottom: 10px;
            text-align: center;
        }
        .form-section {
            background: #1a1a1a;
            border: 1px solid #00ff00;
            padding: 20px;
            margin: 20px 0;
            border-radius: 5px;
        }
        input[type="text"] {
            width: 100%;
            padding: 12px;
            margin: 10px 0;
            background: #002200;
            color: #00ff00;
            border: 1px solid #00ff00;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
            font-size: 16px;
            box-sizing: border-box;
        }
        button {
            width: 100%;
            padding: 15px;
            background: #00aa00;
            color: #000;
            border: none;
            border-radius: 3px;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.3s;
        }
        button:hover {
            background: #00ff00;
        }
        button:disabled {
            background: #333;
            color: #666;
            cursor: not-allowed;
        }
        .result {
            padding: 15px;
            margin: 15px 0;
            border-radius: 3px;
        }
        .success {
            background: #002200;
            border: 1px solid #00ff00;
            color: #00ff00;
        }
        .error {
            background: #220000;
            border: 1px solid #ff0000;
            color: #ff0000;
        }
        .info {
            background: #000022;
            border: 1px solid #0000ff;
            color: #6666ff;
        }
        .note {
            color: #888;
            font-size: 12px;
            margin-top: 10px;
        }
    </style>
</head>
<body>
    <h1>💧 RustChain Testnet Faucet</h1>
    
    <div class="form-section">
        <p>Get free test RTC tokens for development.</p>
        <form id="faucetForm">
            <label for="wallet">Your RTC Wallet Address:</label>
            <input type="text" id="wallet" name="wallet" placeholder="0x..." required>
            <button type="submit" id="submitBtn">Get Test RTC</button>
        </form>
        
        <div id="result"></div>
    </div>
    
    <div class="note">
        <p><strong>Rate Limit:</strong> {{ rate_limit }} RTC per {{ hours }} hours per IP</p>
        <p><strong>Network:</strong> RustChain Testnet</p>
    </div>

    <script>
        const form = document.getElementById('faucetForm');
        const result = document.getElementById('result');
        const submitBtn = document.getElementById('submitBtn');
        
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            submitBtn.disabled = true;
            submitBtn.textContent = 'Requesting...';
            result.innerHTML = '';
            
            const wallet = document.getElementById('wallet').value;
            
            try {
                const response = await fetch('/faucet/drip', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({wallet})
                });
                
                const data = await response.json();
                
                if (data.ok) {
                    result.textContent = '';
                    const successDiv = document.createElement('div');
                    successDiv.className = 'result success';
                    successDiv.textContent = '✅ Success! Sent ' + data.amount + ' RTC to ' + wallet;
                    result.appendChild(successDiv);
                    if (data.next_available) {
                        const infoDiv = document.createElement('div');
                        infoDiv.className = 'result info';
                        infoDiv.textContent = 'Next available: ' + data.next_available;
                        result.appendChild(infoDiv);
                    }
                } else {
                    result.textContent = '';
                    const errorDiv = document.createElement('div');
                    errorDiv.className = 'result error';
                    errorDiv.textContent = '❌ ' + data.error;
                    result.appendChild(errorDiv);
                    if (data.next_available) {
                        const infoDiv = document.createElement('div');
                        infoDiv.className = 'result info';
                        infoDiv.textContent = 'Next available: ' + data.next_available;
                        result.appendChild(infoDiv);
                    }
                }
            } catch (err) {
                result.textContent = '';
                const errDiv = document.createElement('div');
                errDiv.className = 'result error';
                errDiv.textContent = '❌ Error: ' + err.message;
                result.appendChild(errDiv);
            }
            
            submitBtn.disabled = false;
            submitBtn.textContent = 'Get Test RTC';
        });
    </script>
</body>
</html>
"""


@app.route('/')
def index():
    """Serve the faucet homepage."""
    return render_template_string(HTML_TEMPLATE, rate_limit=MAX_DRIP_AMOUNT, hours=RATE_LIMIT_HOURS)


@app.route('/faucet')
def faucet_page():
    """Serve the faucet page (alias for index)."""
    return render_template_string(HTML_TEMPLATE, rate_limit=MAX_DRIP_AMOUNT, hours=RATE_LIMIT_HOURS)


@app.route('/faucet/drip', methods=['POST'])
def drip():
    """
    Handle drip requests.
    
    Request body:
        {"wallet": "0x..."}
    
    Response:
        {"ok": true, "amount": 0.5, "next_available": "2026-03-08T12:00:00Z"}
    """
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"ok": False, "error": "Invalid JSON payload"}), 400
    
    if not data or 'wallet' not in data:
        return jsonify({'ok': False, 'error': 'Wallet address required'}), 400
    
    wallet = data['wallet'].strip()
    
    # Basic wallet validation (should start with 0x and be reasonably long)
    if not wallet.startswith('0x') or len(wallet) < 10:
        return jsonify({'ok': False, 'error': 'Invalid wallet address'}), 400
    
    ip = get_client_ip()

    # Check rate limit for IP
    if not can_drip(ip):
        next_available = get_next_available(ip)
        return jsonify({
            'ok': False,
            'error': 'IP rate limit exceeded',
            'next_available': next_available
        }), 429

    # Check rate limit for Wallet
    if not can_drip(wallet, is_wallet=True):
        next_available = get_next_available(wallet, is_wallet=True)
        return jsonify({
            'ok': False,
            'error': 'Wallet rate limit exceeded',
            'next_available': next_available
        }), 429
    # Record the drip (in production, this would actually transfer tokens)
    # For now, we simulate the drip
    amount = MAX_DRIP_AMOUNT
    record_drip(wallet, ip, amount)
    
    return jsonify({
        'ok': True,
        'amount': amount,
        'wallet': wallet,
        'next_available': (datetime.now() + timedelta(hours=RATE_LIMIT_HOURS)).isoformat()
    })


if __name__ == '__main__':
    # Initialize database
    if not os.path.exists(DATABASE):
        init_db()
    else:
        init_db()  # Ensure table exists
    
    # Run the server
    print("Starting RustChain Faucet on http://0.0.0.0:8090/faucet")
    app.run(host='0.0.0.0', port=8090, debug=False)
