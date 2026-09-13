#!/usr/bin/env python3
"""
RustChain Testnet Faucet -- DEMO ONLY, DOES NOT PAY.

    #############################################################
    # DEMO - records requests, does not pay.                    #
    # This module contains NO node call. Every "successful"      #
    # drip only writes a row into drip_requests; no RTC ever     #
    # leaves any wallet.                                         #
    #                                                            #
    # The supported, paying faucet is faucet_service/            #
    # faucet_service.py (POST /wallet/transfer with X-Admin-Key, #
    # records tx_hash, shipped as                                #
    # testnet/systemd/rustchain-testnet-faucet.service).         #
    # See FAUCET.md.                                             #
    #############################################################

Kept in-tree as a minimal reference implementation of the rate-limiting /
validation logic. Do not deploy it as a faucet: it answers every caller with
a success payload, so operators and users alike are told tokens were sent
when nothing was sent (issue #8243, fallout from #8240).

Features (all local, none of them transfer value):
- IP-based rate limiting
- SQLite backend for tracking
- Simple HTML form for requesting tokens
"""

import sqlite3
import time
import os
import re
from datetime import datetime, timedelta, timezone
from flask import Flask, request, jsonify, render_template_string
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
DATABASE = 'faucet.db'
RTC_WALLET_RE = re.compile(r'^RTC[0-9a-fA-F]{40}$')

# DEMO - records requests, does not pay.
# Nothing in this module talks to a node. Exposed in the API payload and in
# the UI so that neither a caller nor an operator can mistake a recorded
# request for a settled transfer.
DEMO_MODE = True
DEMO_NOTICE = (
    'DEMO faucet: your request was recorded, but no RTC was sent. '
    'The paying faucet is faucet_service/faucet_service.py (see FAUCET.md).'
)

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


def parse_drip_timestamp(timestamp):
    """Parse a stored drip timestamp as UTC when SQLite returns it without tzinfo."""
    drip_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
    if drip_time.tzinfo is None:
        return drip_time.replace(tzinfo=timezone.utc)
    return drip_time


def can_drip(identifier, is_wallet=False):
    """Check if the IP or Wallet can request a drip (rate limiting)."""
    last_time = get_last_drip_time(identifier, is_wallet)
    if not last_time:
        return True
    
    last_drip = parse_drip_timestamp(last_time)
    now = datetime.now(timezone.utc)
    hours_since = (now - last_drip).total_seconds() / 3600

    return hours_since >= RATE_LIMIT_HOURS


def get_next_available(identifier, is_wallet=False):
    """Get the next available time for this IP or wallet."""
    last_time = get_last_drip_time(identifier, is_wallet)
    if not last_time:
        return None
    
    last_drip = parse_drip_timestamp(last_time)
    next_available = last_drip + timedelta(hours=RATE_LIMIT_HOURS)
    now = datetime.now(timezone.utc)
    
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


def try_record_drip(wallet, ip_address, amount):
    """Atomically check rate limits and record a drip request.

    Uses BEGIN IMMEDIATE to prevent TOCTOU race conditions.
    Returns (success, error_message, next_available).
    """
    conn = sqlite3.connect(DATABASE)
    try:
        conn.execute('BEGIN IMMEDIATE')
        c = conn.cursor()

        # Check IP rate limit
        c.execute('''
            SELECT timestamp FROM drip_requests
            WHERE ip_address = ?
            ORDER BY timestamp DESC
            LIMIT 1
        ''', (ip_address,))
        row = c.fetchone()
        if row:
            last_drip = parse_drip_timestamp(row[0])
            now = datetime.now(timezone.utc)
            hours_since = (now - last_drip).total_seconds() / 3600
            if hours_since < RATE_LIMIT_HOURS:
                next_available = last_drip + timedelta(hours=RATE_LIMIT_HOURS)
                conn.rollback()
                return (False, 'IP rate limit exceeded', next_available.isoformat())

        # Check wallet rate limit
        c.execute('''
            SELECT timestamp FROM drip_requests
            WHERE wallet = ?
            ORDER BY timestamp DESC
            LIMIT 1
        ''', (wallet,))
        row = c.fetchone()
        if row:
            last_drip = parse_drip_timestamp(row[0])
            now = datetime.now(timezone.utc)
            hours_since = (now - last_drip).total_seconds() / 3600
            if hours_since < RATE_LIMIT_HOURS:
                next_available = last_drip + timedelta(hours=RATE_LIMIT_HOURS)
                conn.rollback()
                return (False, 'Wallet rate limit exceeded', next_available.isoformat())

        # Record the drip
        c.execute('''
            INSERT INTO drip_requests (wallet, ip_address, amount)
            VALUES (?, ?, ?)
        ''', (wallet, ip_address, amount))
        conn.commit()
        return (True, None, None)

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def is_valid_wallet_address(wallet):
    """Accept legacy Ethereum-style wallets and native RTC wallets.

    For 0x-prefixed addresses, enforces exactly 42 chars (0x + 40 hex),
    matching standard Ethereum address format.
    For RTC addresses, enforces RTC + exactly 40 hex chars.
    """
    if wallet.startswith('0x'):
        if len(wallet) != 42:
            return False
        return all(c in '0123456789abcdefABCDEF' for c in wallet[2:])
    return bool(RTC_WALLET_RE.fullmatch(wallet))


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
    <h1>💧 RustChain Testnet Faucet <small>(DEMO)</small></h1>

    <div class="result error">
        <strong>DEMO ONLY — this page does not pay.</strong>
        Requests are recorded for rate-limit testing; no RTC is transferred.
        The paying faucet is <code>faucet_service/faucet_service.py</code>.
    </div>

    <div class="form-section">
        <p>Record a test drip request. <strong>No tokens are sent.</strong></p>
        <form id="faucetForm">
            <label for="wallet">Your RTC Wallet Address:</label>
            <input type="text" id="wallet" name="wallet" placeholder="0x..." required>
            <button type="submit" id="submitBtn">Record Demo Request</button>
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
                    successDiv.textContent = '📝 Request recorded for ' + wallet
                        + ' (' + data.amount + ' RTC). DEMO — no RTC was sent.';
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
            submitBtn.textContent = 'Record Demo Request';
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
    Record a drip request. DEMO - records requests, does not pay.

    No transfer is attempted: `ok` means "request accepted and recorded",
    NOT "tokens sent". `sent` is always False here so that callers can tell
    the two apart; the paying implementation lives in faucet_service/.

    Request body:
        {"wallet": "0x..."}

    Response:
        {"ok": true, "sent": false, "demo": true, "amount": 0.5,
         "notice": "DEMO faucet: ... no RTC was sent",
         "next_available": "2026-03-08T12:00:00Z"}
    """
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({'ok': False, 'error': 'Invalid JSON body'}), 400

    if 'wallet' not in data:
        return jsonify({'ok': False, 'error': 'Wallet address required'}), 400

    wallet_value = data['wallet']
    if not isinstance(wallet_value, str):
        return jsonify({'ok': False, 'error': 'Invalid wallet address'}), 400

    wallet = wallet_value.strip()

    if len(wallet) > 128:
        return jsonify({'ok': False, 'error': 'Wallet address too long'}), 400

    # Basic wallet validation (accept Ethereum-style and native RTC wallets)
    if not is_valid_wallet_address(wallet):
        return jsonify({'ok': False, 'error': 'Invalid wallet address'}), 400
    
    ip = get_client_ip()

    amount = MAX_DRIP_AMOUNT
    success, error, next_available = try_record_drip(wallet, ip, amount)

    if not success:
        return jsonify({
            'ok': False,
            'error': error,
            'next_available': next_available
        }), 429

    return jsonify({
        'ok': True,
        # DEMO - records requests, does not pay. `amount` is the amount that
        # was charged against the rate limit, not an amount that was sent.
        'sent': False,
        'demo': DEMO_MODE,
        'tx_hash': None,
        'notice': DEMO_NOTICE,
        'amount': amount,
        'wallet': wallet,
        'next_available': (datetime.now(timezone.utc) + timedelta(hours=RATE_LIMIT_HOURS)).isoformat()
    })


if __name__ == '__main__':
    # Initialize database
    if not os.path.exists(DATABASE):
        init_db()
    else:
        init_db()  # Ensure table exists
    
    # Run the server
    print("=" * 70)
    print("DEMO FAUCET - records requests, DOES NOT PAY.")
    print("No RTC is transferred by this process. Callers are told so in the")
    print("JSON payload ('sent': false) and on the web page.")
    print("The supported paying faucet is faucet_service/faucet_service.py")
    print("(see FAUCET.md). Do not deploy this file as a public faucet.")
    print("=" * 70)
    print("Starting RustChain DEMO Faucet on http://0.0.0.0:8090/faucet")
    app.run(host='0.0.0.0', port=8090, debug=False)
