#!/usr/bin/env python3
"""
RustChain Testnet Faucet
A simple Flask web application that dispenses test RTC tokens.

Features:
- Wallet-based rate limiting (SECURITY FIX)
- Captcha verification (SECURITY FIX)
- SQLite backend for tracking
- Simple HTML form for requesting tokens

SECURITY FIX: Fixed X-Forwarded-For spoofing vulnerability (Issue #2246)
"""

import sqlite3
import time
import os
import hashlib
import secrets
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template_string, session

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', secrets.token_hex(32))
DATABASE = 'faucet.db'

# Rate limiting settings (per 24 hours)
MAX_DRIP_AMOUNT = 0.5  # RTC
RATE_LIMIT_HOURS = 24

# Captcha settings (simple math captcha for demo)
CAPTCHA_ENABLED = os.environ.get('CAPTCHA_ENABLED', 'true').lower() == 'true'


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
    c.execute('''
        CREATE TABLE IF NOT EXISTS captcha_sessions (
            id TEXT PRIMARY KEY,
            answer INTEGER NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()


def get_client_ip():
    """Get client IP address from request.
    
    SECURITY FIX: Never trust X-Forwarded-For header from clients.
    Always use remote_addr for rate limiting to prevent IP spoofing.
    """
    # SECURITY: Always use the actual remote address, never trust client headers
    return request.remote_addr or '127.0.0.1'


def generate_captcha():
    """Generate a simple math captcha."""
    num1 = secrets.randbelow(10) + 1
    num2 = secrets.randbelow(10) + 1
    captcha_id = secrets.token_hex(16)
    answer = num1 + num2
    
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('INSERT INTO captcha_sessions (id, answer) VALUES (?, ?)', 
              (captcha_id, answer))
    conn.commit()
    conn.close()
    
    return captcha_id, f"{num1} + {num2} = ?"


def verify_captcha(captcha_id, user_answer):
    """Verify captcha response."""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT answer FROM captcha_sessions WHERE id = ? AND created_at > datetime("now", "-5 minutes")', 
              (captcha_id,))
    result = c.fetchone()
    if result:
        c.execute('DELETE FROM captcha_sessions WHERE id = ?', (captcha_id,))
        conn.commit()
    conn.close()
    
    if result and result[0] == int(user_answer):
        return True
    return False


def get_last_drip_time(wallet):
    """Get the last time this wallet requested a drip."""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''
        SELECT timestamp FROM drip_requests
        WHERE wallet = ?
        ORDER BY timestamp DESC
        LIMIT 1
    ''', (wallet,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None


def can_drip(wallet):
    """Check if the wallet can request a drip (wallet-based rate limiting)."""
    last_time = get_last_drip_time(wallet)
    if not last_time:
        return True
    
    last_drip = datetime.fromisoformat(last_time.replace('Z', '+00:00'))
    now = datetime.now(last_drip.tzinfo)
    hours_since = (now - last_drip).total_seconds() / 3600
    
    return hours_since >= RATE_LIMIT_HOURS


def record_drip(wallet, ip_address, amount):
    """Record a drip request in the database."""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''
        INSERT INTO drip_requests (wallet, ip_address, amount)
        VALUES (?, ?, ?)
    ''', (wallet, ip_address, amount))
    conn.commit()
    conn.close()


@app.route('/')
def index():
    """Render the faucet HTML page."""
    captcha_id, captcha_question = generate_captcha() if CAPTCHA_ENABLED else (None, None)
    
    html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>RustChain Testnet Faucet</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; }
            input, button { padding: 10px; margin: 5px 0; width: 100%; box-sizing: border-box; }
            button { background: #4CAF50; color: white; border: none; cursor: pointer; }
            button:hover { background: #45a049; }
            .error { color: red; }
            .success { color: green; }
            .captcha { background: #f0f0f0; padding: 10px; margin: 10px 0; }
        </style>
    </head>
    <body>
        <h1>🚰 RustChain Testnet Faucet</h1>
        <p>Request test RTC tokens for development.</p>
        <p><strong>Limit:</strong> 0.5 RTC per wallet per 24 hours</p>
        
        <form id="faucet-form">
            <label>Wallet Address:</label>
            <input type="text" id="wallet" name="wallet" required 
                   placeholder="RTC..." pattern="RTC[a-zA-Z0-9]{39}">
            
            ''' + ('''
            <div class="captcha">
                <label>Security Check: <span id="captcha-question">{{question}}</span></label>
                <input type="hidden" id="captcha-id" name="captcha_id" value="{{captcha_id}}">
                <input type="number" id="captcha-answer" name="captcha_answer" required 
                       placeholder="Your answer">
            </div>
            ''' if CAPTCHA_ENABLED else '') + '''
            
            <button type="submit">Request 0.5 RTC</button>
        </form>
        
        <div id="result"></div>
        
        <script>
        document.getElementById('faucet-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const wallet = document.getElementById('wallet').value;
            const captchaId = document.getElementById('captcha-id')?.value;
            const captchaAnswer = document.getElementById('captcha-answer')?.value;
            
            const params = new URLSearchParams({ wallet });
            if (captchaId) params.append('captcha_id', captchaId);
            if (captchaAnswer) params.append('captcha_answer', captchaAnswer);
            
            const response = await fetch('/drip?' + params.toString());
            const result = await response.json();
            
            const resultDiv = document.getElementById('result');
            resultDiv.className = result.success ? 'success' : 'error';
            resultDiv.textContent = result.message;
        });
        </script>
    </body>
    </html>
    '''.replace('{{question}}', captcha_question or '').replace('{{captcha_id}}', captcha_id or '')
    
    return render_template_string(html)


@app.route('/drip')
def drip():
    """Dispense test RTC tokens."""
    wallet = request.args.get('wallet')
    
    if not wallet or not wallet.startswith('RTC'):
        return jsonify({'success': False, 'message': 'Invalid wallet address'}), 400
    
    # Verify captcha if enabled
    if CAPTCHA_ENABLED:
        captcha_id = request.args.get('captcha_id')
        captcha_answer = request.args.get('captcha_answer')
        if not captcha_id or not captcha_answer:
            return jsonify({'success': False, 'message': 'Captcha required'}), 400
        if not verify_captcha(captcha_id, captcha_answer):
            return jsonify({'success': False, 'message': 'Invalid captcha'}), 400
    
    # Get client IP (SECURITY: uses remote_addr, not X-Forwarded-For)
    ip_address = get_client_ip()
    
    # Check wallet-based rate limit
    if not can_drip(wallet):
        return jsonify({
            'success': False, 
            'message': 'Rate limit exceeded. Please wait 24 hours before requesting again.'
        }), 429
    
    # Record the drip
    record_drip(wallet, ip_address, MAX_DRIP_AMOUNT)
    
    # TODO: Actually send RTC tokens via blockchain transaction
    # For now, just record the request
    
    return jsonify({
        'success': True,
        'message': f'Successfully requested {MAX_DRIP_AMOUNT} RTC to {wallet}',
        'wallet': wallet,
        'amount': MAX_DRIP_AMOUNT
    })


@app.route('/health')
def health():
    """Health check endpoint."""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=False)
