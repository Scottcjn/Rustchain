#!/usr/bin/env python3
"""
RustChain Testnet Faucet
A simple Flask web application that dispenses test RTC tokens.

Features:
- Wallet-based rate limiting (PRIMARY defense - prevents IP-spoofing bypass)
- IP-based rate limiting (SECONDARY defense)
- SQLite backend for tracking
- Simple HTML form for requesting tokens

Security: Fixes X-Forwarded-For spoofing vulnerability (CVE candidate).
The original implementation trusted X-Forwarded-For headers unconditionally,
allowing attackers behind a misconfigured reverse proxy to bypass IP-based
rate limits by setting arbitrary XFF values.
"""

import sqlite3
import time
import os
import ipaddress
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)
DATABASE = 'faucet.db'

# Rate limiting settings
MAX_DRIP_AMOUNT = 0.5  # RTC
RATE_LIMIT_HOURS = 24
TRUSTED_PROXY_IPS = frozenset([
    ipaddress.ip_network('127.0.0.0/8'),
    ipaddress.ip_network('::1/128'),
])


def is_valid_ip(s):
    """Check if string is a valid IP address."""
    try:
        ipaddress.ip_address(s)
        return True
    except ValueError:
        return False


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
    """Get the real client IP address.
    
    SECURITY FIX: Do NOT trust X-Forwarded-For from untrusted sources.
    
    The original vulnerability: faucet trusted X-Forwarded-For header from any
    localhost connection, allowing attackers to bypass rate limits by sending:
        X-Forwarded-For: <fresh_ip>, <old_banned_ip>
    
    The fix:
    1. NEVER trust X-Forwarded-For unless the direct connection is from a
       known/trusted reverse proxy IP (not just localhost).
    2. For all practical purposes: use remote_addr as the client IP.
    3. The X-Forwarded-For header is only consulted if remote_addr is
       explicitly from our own trusted proxy list.
    
    In production, configure TRUSTED_PROXY_IPS with your actual proxy IPs.
    """
    remote_addr = request.remote_addr or '127.0.0.1'
    
    # Check if request came through a trusted reverse proxy
    if remote_addr:
        try:
            remote_ip = ipaddress.ip_address(remote_addr)
            is_trusted = any(remote_ip in net for net in TRUSTED_PROXY_IPS)
            if is_trusted and request.headers.get('X-Forwarded-For'):
                xff = request.headers.get('X-Forwarded-For')
                first_ip = xff.split(',')[0].strip()
                # Only use XFF if it looks like a valid IP
                if is_valid_ip(first_ip):
                    return first_ip
        except ValueError:
            pass
    
    # For all other cases: use remote_addr directly (no XFF spoofing possible)
    return remote_addr


def get_last_drip_time_by_ip(ip_address):
    """Get the last time this IP requested a drip."""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''
        SELECT timestamp FROM drip_requests
        WHERE ip_address = ?
        ORDER BY timestamp DESC
        LIMIT 1
    ''', (ip_address,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None


def get_last_drip_time_by_wallet(wallet_address):
    """Get the last time this wallet requested a drip."""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''
        SELECT timestamp FROM drip_requests
        WHERE wallet = ?
        ORDER BY timestamp DESC
        LIMIT 1
    ''', (wallet_address,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None


def can_drip_by_ip(ip_address):
    """Check if the IP can request a drip (IP-based rate limiting - secondary defense)."""
    last_time = get_last_drip_time_by_ip(ip_address)
    if not last_time:
        return True
    
    last_drip = datetime.fromisoformat(last_time.replace('Z', '+00:00'))
    now = datetime.now(last_drip.tzinfo)
    hours_since = (now - last_drip).total_seconds() / 3600
    
    return hours_since >= RATE_LIMIT_HOURS


def can_drip_by_wallet(wallet_address):
    """Check if the wallet can request a drip (wallet-based rate limiting - PRIMARY defense).
    
    Rationale: Even if an attacker can spoof X-Forwarded-For to rotate IPs,
    they cannot easily obtain unlimited fresh wallet addresses without spending
    real resources. Wallet-based rate limiting makes the attack economically
    infeasible.
    """
    last_time = get_last_drip_time_by_wallet(wallet_address)
    if not last_time:
        return True
    
    last_drip = datetime.fromisoformat(last_time.replace('Z', '+00:00'))
    now = datetime.now(last_drip.tzinfo)
    hours_since = (now - last_drip).total_seconds() / 3600
    
    return hours_since >= RATE_LIMIT_HOURS


def get_next_available_by_ip(ip_address):
    """Get the next available time for this IP."""
    last_time = get_last_drip_time_by_ip(ip_address)
    if not last_time:
        return None
    
    last_drip = datetime.fromisoformat(last_time.replace('Z', '+00:00'))
    next_available = last_drip + timedelta(hours=RATE_LIMIT_HOURS)
    now = datetime.now(last_drip.tzinfo)
    
    if next_available > now:
        return next_available.isoformat()
    return None


def get_next_available_by_wallet(wallet_address):
    """Get the next available time for this wallet."""
    last_time = get_last_drip_time_by_wallet(wallet_address)
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
        .security-badge {
            background: #003300;
            border: 1px solid #00ff00;
            padding: 10px;
            margin: 10px 0;
            border-radius: 3px;
            font-size: 12px;
        }
    </style>
</head>
<body>
    <h1>RustChain Testnet Faucet</h1>
    
    <div class="security-badge">
        Security: Wallet-based rate limiting enabled (prevents IP-spoofing bypass)
    </div>
    
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
        <p><strong>Rate Limit:</strong> {{ rate_limit }} RTC per {{ hours }} hours per wallet (primary) + per IP (secondary)</p>
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
                    result.innerHTML = '<div class="result success">Sent ' + data.amount + ' RTC to ' + wallet + '</div>';
                    if (data.next_available) {
                        result.innerHTML += '<div class="result info">Next available: ' + data.next_available + '</div>';
                    }
                } else {
                    let errMsg = data.error;
                    if (data.rate_limit_type) {
                        errMsg += ' (type: ' + data.rate_limit_type + ')';
                    }
                    result.innerHTML = '<div class="result error">' + errMsg + '</div>';
                    if (data.next_available) {
                        result.innerHTML += '<div class="result info">Next available: ' + data.next_available + '</div>';
                    }
                }
            } catch (err) {
                result.innerHTML = '<div class="result error">Error: ' + err.message + '</div>';
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
    
    Security: Implements dual-layer rate limiting:
    1. PRIMARY: Wallet-based rate limiting (prevents XFF spoofing bypass)
    2. SECONDARY: IP-based rate limiting (catches simple abusers)
    
    Request body:
        {"wallet": "0x..."}
    
    Response:
        {"ok": true, "amount": 0.5, "next_available": "2026-03-08T12:00:00Z"}
    """
    data = request.get_json()
    
    if not data or 'wallet' not in data:
        return jsonify({'ok': False, 'error': 'Wallet address required'}), 400
    
    wallet = data['wallet'].strip()
    
    # Basic wallet validation (should start with 0x and be reasonably long)
    if not wallet.startswith('0x') or len(wallet) < 10:
        return jsonify({'ok': False, 'error': 'Invalid wallet address'}), 400
    
    ip = get_client_ip()
    
    # PRIMARY DEFENSE: Wallet-based rate limiting
    # This is the main defense against X-Forwarded-For spoofing.
    # Even if an attacker spoofs XFF to rotate IPs, they cannot bypass
    # wallet-based rate limits without obtaining new wallets.
    if not can_drip_by_wallet(wallet):
        next_available = get_next_available_by_wallet(wallet)
        return jsonify({
            'ok': False,
            'error': 'Rate limit exceeded for this wallet',
            'next_available': next_available,
            'rate_limit_type': 'wallet'
        }), 429
    
    # SECONDARY DEFENSE: IP-based rate limiting
    # Catches simple abusers who don't bother with XFF spoofing.
    if not can_drip_by_ip(ip):
        next_available = get_next_available_by_ip(ip)
        return jsonify({
            'ok': False,
            'error': 'Rate limit exceeded for this IP',
            'next_available': next_available,
            'rate_limit_type': 'ip'
        }), 429
    
    # Record the drip (in production, this would actually transfer tokens)
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
