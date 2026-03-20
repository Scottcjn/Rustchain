// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT
"""
RustChain Testnet Faucet Service
Provides free test RTC to developers with rate limiting and GitHub OAuth integration.
"""

from flask import Flask, request, jsonify, render_template_string, redirect, url_for, session
import sqlite3
import time
import hashlib
import secrets
import requests
import json
from datetime import datetime, timedelta
from contextlib import contextmanager

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

DB_PATH = 'faucet.db'
FAUCET_AMOUNT = 1.0
RATE_LIMIT_HOURS = 24
GITHUB_CLIENT_ID = None  # Set via environment or config
GITHUB_CLIENT_SECRET = None  # Set via environment or config

@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    with get_db() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS faucet_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wallet_address TEXT NOT NULL,
                github_username TEXT,
                ip_address TEXT NOT NULL,
                amount REAL NOT NULL,
                timestamp INTEGER NOT NULL,
                tx_hash TEXT,
                status TEXT DEFAULT 'pending'
            )
        ''')
        conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_wallet_time ON faucet_requests(wallet_address, timestamp)
        ''')
        conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_github_time ON faucet_requests(github_username, timestamp)
        ''')
        conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_ip_time ON faucet_requests(ip_address, timestamp)
        ''')
        conn.commit()

def check_rate_limit(wallet_address, github_username=None, ip_address=None):
    cutoff_time = int(time.time()) - (RATE_LIMIT_HOURS * 3600)

    with get_db() as conn:
        # Check wallet address rate limit
        result = conn.execute(
            'SELECT COUNT(*) as count FROM faucet_requests WHERE wallet_address = ? AND timestamp > ?',
            (wallet_address, cutoff_time)
        ).fetchone()

        if result['count'] > 0:
            return False, 'Wallet address already used within 24 hours'

        # Check GitHub username if provided (more lenient)
        if github_username:
            result = conn.execute(
                'SELECT COUNT(*) as count FROM faucet_requests WHERE github_username = ? AND timestamp > ?',
                (github_username, cutoff_time)
            ).fetchone()

            if result['count'] > 0:
                return False, 'GitHub account already used within 24 hours'
        else:
            # Stricter IP-based rate limiting for non-authenticated requests
            result = conn.execute(
                'SELECT COUNT(*) as count FROM faucet_requests WHERE ip_address = ? AND timestamp > ?',
                (ip_address, cutoff_time)
            ).fetchone()

            if result['count'] >= 3:  # Allow 3 per IP without GitHub auth
                return False, 'IP address rate limit exceeded (authenticate with GitHub for higher limits)'

    return True, None

def verify_github_user(username, access_token=None):
    """Verify GitHub username exists and optionally validate access token"""
    try:
        headers = {}
        if access_token:
            headers['Authorization'] = f'token {access_token}'

        response = requests.get(f'https://api.github.com/users/{username}', headers=headers, timeout=10)

        if response.status_code == 200:
            user_data = response.json()
            return True, user_data
        elif response.status_code == 404:
            return False, 'GitHub user not found'
        else:
            return False, 'GitHub API error'
    except Exception as e:
        return False, f'Error verifying GitHub user: {str(e)}'

def create_faucet_transaction(wallet_address, amount):
    """Create a transaction sending test RTC to the wallet address"""
    # This would integrate with the actual blockchain code
    # For now, return a mock pending transaction
    tx_id = hashlib.sha256(f"{wallet_address}{amount}{time.time()}".encode()).hexdigest()[:16]
    return tx_id

@app.route('/faucet')
def faucet_page():
    github_user = session.get('github_user')
    error = request.args.get('error')
    success = request.args.get('success')

    template = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>RustChain Testnet Faucet</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; }
            .form-group { margin-bottom: 20px; }
            label { display: block; margin-bottom: 5px; font-weight: bold; }
            input[type="text"] { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; }
            button { background: #007cba; color: white; padding: 12px 24px; border: none; border-radius: 4px; cursor: pointer; }
            button:hover { background: #005a85; }
            .github-auth { background: #24292e; color: white; text-decoration: none; padding: 10px 20px; border-radius: 4px; display: inline-block; margin: 10px 0; }
            .github-auth:hover { background: #1a1e22; }
            .error { background: #f8d7da; color: #721c24; padding: 10px; border-radius: 4px; margin: 10px 0; }
            .success { background: #d4edda; color: #155724; padding: 10px; border-radius: 4px; margin: 10px 0; }
            .user-info { background: #e7f3ff; padding: 10px; border-radius: 4px; margin: 10px 0; }
        </style>
    </head>
    <body>
        <h1>🚰 RustChain Testnet Faucet</h1>
        <p>Get <strong>1 free test RTC</strong> for development and testing.</p>

        {% if error %}
        <div class="error">{{ error }}</div>
        {% endif %}

        {% if success %}
        <div class="success">{{ success }}</div>
        {% endif %}

        {% if github_user %}
        <div class="user-info">
            ✅ Authenticated as <strong>{{ github_user.login }}</strong>
            <a href="{{ url_for('github_logout') }}" style="margin-left: 20px;">Logout</a>
        </div>
        {% else %}
        <div>
            <a href="{{ url_for('github_login') }}" class="github-auth">🔗 Login with GitHub (Higher Limits)</a>
        </div>
        {% endif %}

        <form method="POST" action="{{ url_for('faucet_drip') }}">
            <div class="form-group">
                <label for="wallet">RTC Wallet Address:</label>
                <input type="text" id="wallet" name="wallet" required
                       placeholder="your-test-wallet-address" />
            </div>

            <button type="submit">💰 Request 1 Test RTC</button>
        </form>

        <hr style="margin: 40px 0;">
        <h3>📋 Recent Requests</h3>
        <div id="recent-requests">
            {% for req in recent_requests %}
            <div style="background: #f8f9fa; padding: 10px; margin: 5px 0; border-radius: 4px;">
                <strong>{{ req.wallet_address[:20] }}...</strong>
                - {{ req.amount }} RTC
                - {{ req.status }}
                {% if req.github_username %}
                (via @{{ req.github_username }})
                {% endif %}
                <small>{{ req.time_ago }}</small>
            </div>
            {% endfor %}
        </div>

        <hr style="margin: 40px 0;">
        <h3>📖 API Usage</h3>
        <pre style="background: #f8f9fa; padding: 15px; border-radius: 4px; overflow-x: auto;">
POST /faucet/drip
{
  "wallet": "your-wallet-address",
  "github_username": "your-github-username"  // optional
}

Response:
{
  "ok": true,
  "amount": 1.0,
  "pending_id": 123,
  "next_available": "2024-01-01T12:00:00Z"
}
        </pre>
    </body>
    </html>
    '''

    # Get recent requests for display
    with get_db() as conn:
        rows = conn.execute('''
            SELECT wallet_address, github_username, amount, status, timestamp
            FROM faucet_requests
            ORDER BY timestamp DESC
            LIMIT 10
        ''').fetchall()

        recent_requests = []
        for row in rows:
            time_ago = datetime.fromtimestamp(row['timestamp']).strftime('%Y-%m-%d %H:%M')
            recent_requests.append({
                'wallet_address': row['wallet_address'],
                'github_username': row['github_username'],
                'amount': row['amount'],
                'status': row['status'],
                'time_ago': time_ago
            })

    return render_template_string(template,
                                github_user=github_user,
                                error=error,
                                success=success,
                                recent_requests=recent_requests)

@app.route('/faucet/drip', methods=['POST'])
def faucet_drip():
    client_ip = request.remote_addr

    if request.is_json:
        data = request.get_json()
        wallet_address = data.get('wallet', '').strip()
        github_username = data.get('github_username', '').strip() or None
    else:
        wallet_address = request.form.get('wallet', '').strip()
        github_username = session.get('github_user', {}).get('login')

    if not wallet_address:
        if request.is_json:
            return jsonify({'ok': False, 'error': 'Wallet address required'}), 400
        else:
            return redirect(url_for('faucet_page', error='Wallet address required'))

    # Basic wallet address validation
    if len(wallet_address) < 10 or len(wallet_address) > 100:
        error_msg = 'Invalid wallet address format'
        if request.is_json:
            return jsonify({'ok': False, 'error': error_msg}), 400
        else:
            return redirect(url_for('faucet_page', error=error_msg))

    # Check rate limits
    allowed, rate_error = check_rate_limit(wallet_address, github_username, client_ip)
    if not allowed:
        if request.is_json:
            return jsonify({'ok': False, 'error': rate_error}), 429
        else:
            return redirect(url_for('faucet_page', error=rate_error))

    # Verify GitHub username if provided
    if github_username:
        valid_github, github_error = verify_github_user(github_username)
        if not valid_github:
            error_msg = f'GitHub verification failed: {github_error}'
            if request.is_json:
                return jsonify({'ok': False, 'error': error_msg}), 400
            else:
                return redirect(url_for('faucet_page', error=error_msg))

    # Create transaction
    try:
        tx_hash = create_faucet_transaction(wallet_address, FAUCET_AMOUNT)

        # Record the request
        with get_db() as conn:
            cursor = conn.execute('''
                INSERT INTO faucet_requests
                (wallet_address, github_username, ip_address, amount, timestamp, tx_hash, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (wallet_address, github_username, client_ip, FAUCET_AMOUNT, int(time.time()), tx_hash, 'pending'))

            request_id = cursor.lastrowid
            conn.commit()

        next_available = datetime.now() + timedelta(hours=RATE_LIMIT_HOURS)

        if request.is_json:
            return jsonify({
                'ok': True,
                'amount': FAUCET_AMOUNT,
                'pending_id': request_id,
                'tx_hash': tx_hash,
                'next_available': next_available.isoformat()
            })
        else:
            success_msg = f'Success! {FAUCET_AMOUNT} RTC sent to {wallet_address[:20]}... (TX: {tx_hash})'
            return redirect(url_for('faucet_page', success=success_msg))

    except Exception as e:
        error_msg = f'Transaction failed: {str(e)}'
        if request.is_json:
            return jsonify({'ok': False, 'error': error_msg}), 500
        else:
            return redirect(url_for('faucet_page', error=error_msg))

@app.route('/faucet/github/login')
def github_login():
    if not GITHUB_CLIENT_ID:
        return redirect(url_for('faucet_page', error='GitHub OAuth not configured'))

    state = secrets.token_urlsafe(32)
    session['oauth_state'] = state

    github_url = (f'https://github.com/login/oauth/authorize'
                 f'?client_id={GITHUB_CLIENT_ID}'
                 f'&redirect_uri={request.url_root}faucet/github/callback'
                 f'&scope=user:email'
                 f'&state={state}')

    return redirect(github_url)

@app.route('/faucet/github/callback')
def github_callback():
    code = request.args.get('code')
    state = request.args.get('state')

    if not code or state != session.get('oauth_state'):
        return redirect(url_for('faucet_page', error='GitHub OAuth failed'))

    # Exchange code for access token
    try:
        token_response = requests.post('https://github.com/login/oauth/access_token', {
            'client_id': GITHUB_CLIENT_ID,
            'client_secret': GITHUB_CLIENT_SECRET,
            'code': code
        }, headers={'Accept': 'application/json'}, timeout=10)

        token_data = token_response.json()
        access_token = token_data.get('access_token')

        if not access_token:
            return redirect(url_for('faucet_page', error='Failed to get GitHub access token'))

        # Get user info
        user_response = requests.get('https://api.github.com/user',
                                   headers={'Authorization': f'token {access_token}'},
                                   timeout=10)

        if user_response.status_code != 200:
            return redirect(url_for('faucet_page', error='Failed to get GitHub user info'))

        user_data = user_response.json()
        session['github_user'] = user_data
        session['github_token'] = access_token

        return redirect(url_for('faucet_page'))

    except Exception as e:
        return redirect(url_for('faucet_page', error=f'GitHub OAuth error: {str(e)}'))

@app.route('/faucet/github/logout')
def github_logout():
    session.pop('github_user', None)
    session.pop('github_token', None)
    session.pop('oauth_state', None)
    return redirect(url_for('faucet_page'))

@app.route('/faucet/stats')
def faucet_stats():
    with get_db() as conn:
        total_requests = conn.execute('SELECT COUNT(*) as count FROM faucet_requests').fetchone()['count']
        total_amount = conn.execute('SELECT COALESCE(SUM(amount), 0) as total FROM faucet_requests').fetchone()['total']

        recent_24h = conn.execute('''
            SELECT COUNT(*) as count FROM faucet_requests
            WHERE timestamp > ?
        ''', (int(time.time()) - 86400,)).fetchone()['count']

        unique_wallets = conn.execute('SELECT COUNT(DISTINCT wallet_address) as count FROM faucet_requests').fetchone()['count']

        github_users = conn.execute('SELECT COUNT(DISTINCT github_username) as count FROM faucet_requests WHERE github_username IS NOT NULL').fetchone()['count']

    return jsonify({
        'total_requests': total_requests,
        'total_amount_distributed': float(total_amount),
        'requests_last_24h': recent_24h,
        'unique_wallets': unique_wallets,
        'github_authenticated_users': github_users
    })

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=False)
