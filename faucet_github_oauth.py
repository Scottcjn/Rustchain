#!/usr/bin/env python3
"""
RustChain Testnet Faucet — GitHub OAuth Enhanced Version
=========================================================

Extends the existing faucet with GitHub OAuth verification for
increased rate limits, as requested in Bounty #751.

| Auth Method           | Limit        |
|-----------------------|--------------|
| No auth (IP only)     | 0.5 RTC/24h  |
| GitHub OAuth          | 1.0 RTC/24h  |
| GitHub account > 1y   | 2.0 RTC/24h  |

Endpoints:
  GET  /faucet              — Web UI (with GitHub login button)
  GET  /faucet/oauth/start  — Start GitHub OAuth flow
  GET  /faucet/oauth/callback — OAuth callback handler
  POST /faucet/drip         — Request tokens (with optional GitHub auth)
  GET  /faucet/status       — Check rate limit status

Usage:
  export GITHUB_CLIENT_ID=your_id
  export GITHUB_CLIENT_SECRET=your_secret
  python faucet_github_oauth.py

Bounty: rustchain-bounties#751 (+5 RTC for GitHub OAuth)
"""

import os
import re
import time
import sqlite3
import secrets
import hashlib
import urllib.parse
from datetime import datetime, timedelta, timezone
from functools import wraps

import requests
from flask import Flask, request, jsonify, render_template_string, session, redirect

# =============================================================================
# Configuration
# =============================================================================

app = Flask(__name__)
app.secret_key = os.environ.get('FAUCET_SECRET_KEY', os.urandom(32).hex())

DATABASE = os.environ.get('FAUCET_DB', 'faucet_oauth.db')
GITHUB_CLIENT_ID = os.environ.get('GITHUB_CLIENT_ID', '')
GITHUB_CLIENT_SECRET = os.environ.get('GITHUB_CLIENT_SECRET', '')
GITHUB_OAUTH_URL = 'https://github.com/login/oauth/authorize'
GITHUB_TOKEN_URL = 'https://github.com/login/oauth/access_token'
GITHUB_API_URL = 'https://api.github.com'

# Rate limits per 24 hours (in RTC)
RATE_LIMITS = {
    'ip_only': 0.5,
    'github_auth': 1.0,
    'github_veteran': 2.0,  # Account age > 1 year
}
RATE_LIMIT_HOURS = 24

# Wallet validation
RTC_WALLET_RE = re.compile(r'^(RTC|0x)[0-9a-fA-F]{40}$')

# =============================================================================
# Database
# =============================================================================

def init_db():
    """Initialize SQLite database with OAuth tracking."""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    # Existing drip requests table (extended)
    c.execute('''
        CREATE TABLE IF NOT EXISTS drip_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wallet TEXT NOT NULL,
            ip_address TEXT NOT NULL,
            github_username TEXT,
            github_account_created_at TEXT,
            amount REAL NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # OAuth sessions table
    c.execute('''
        CREATE TABLE IF NOT EXISTS oauth_sessions (
            state TEXT PRIMARY KEY,
            ip_address TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Index for fast rate-limit lookups
    c.execute('''
        CREATE INDEX IF NOT EXISTS idx_drip_ip
        ON drip_requests(ip_address, timestamp DESC)
    ''')
    c.execute('''
        CREATE INDEX IF NOT EXISTS idx_drip_github
        ON drip_requests(github_username, timestamp DESC)
    ''')

    conn.commit()
    conn.close()


def get_db():
    """Get a database connection."""
    return sqlite3.connect(DATABASE)


def get_last_drip_info(identifier: str, is_github: bool = False):
    """Get last drip time and amount for an identifier."""
    conn = get_db()
    c = conn.cursor()

    if is_github:
        c.execute('''
            SELECT timestamp, amount FROM drip_requests
            WHERE github_username = ?
            ORDER BY timestamp DESC
            LIMIT 1
        ''', (identifier,))
    else:
        c.execute('''
            SELECT timestamp, amount FROM drip_requests
            WHERE ip_address = ?
            ORDER BY timestamp DESC
            LIMIT 1
        ''', (identifier,))

    result = c.fetchone()
    conn.close()

    if not result:
        return None, None

    ts_str, amount = result
    try:
        dt = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt, amount
    except (ValueError, TypeError):
        return None, None


def record_drip(wallet: str, ip_address: str, amount: float,
                github_username: str = None, github_created_at: str = None):
    """Record a drip request."""
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        INSERT INTO drip_requests
        (wallet, ip_address, github_username, github_account_created_at, amount)
        VALUES (?, ?, ?, ?, ?)
    ''', (wallet, ip_address, github_username, github_created_at, amount))
    conn.commit()
    conn.close()


def save_oauth_state(state: str, ip_address: str):
    """Save OAuth state for CSRF protection."""
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        INSERT INTO oauth_sessions (state, ip_address)
        VALUES (?, ?)
    ''', (state, ip_address))
    conn.commit()
    conn.close()


def verify_oauth_state(state: str, ip_address: str) -> bool:
    """Verify OAuth state matches IP and hasn't expired."""
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        SELECT created_at FROM oauth_sessions
        WHERE state = ? AND ip_address = ?
    ''', (state, ip_address))
    result = c.fetchone()

    if result:
        # Delete used state (one-time)
        c.execute('DELETE FROM oauth_sessions WHERE state = ?', (state,))
        conn.commit()

        # Check expiration (10 minutes)
        created = datetime.fromisoformat(result[0].replace('Z', '+00:00'))
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) - created > timedelta(minutes=10):
            conn.close()
            return False
        conn.close()
        return True

    conn.close()
    return False


# =============================================================================
# GitHub OAuth
# =============================================================================

def github_oauth_url(state: str) -> str:
    """Build GitHub OAuth authorization URL."""
    params = {
        'client_id': GITHUB_CLIENT_ID,
        'redirect_uri': request.url_root.rstrip('/') + '/faucet/oauth/callback',
        'scope': 'read:user',
        'state': state,
    }
    return f"{GITHUB_OAUTH_URL}?{urllib.parse.urlencode(params)}"


def exchange_github_code(code: str) -> dict:
    """Exchange OAuth code for access token and user info."""
    # Step 1: Exchange code for token
    token_resp = requests.post(
        GITHUB_TOKEN_URL,
        headers={'Accept': 'application/json'},
        data={
            'client_id': GITHUB_CLIENT_ID,
            'client_secret': GITHUB_CLIENT_SECRET,
            'code': code,
            'redirect_uri': request.url_root.rstrip('/') + '/faucet/oauth/callback',
        },
        timeout=30
    )
    token_resp.raise_for_status()
    token_data = token_resp.json()

    if 'error' in token_data:
        raise RuntimeError(f"GitHub OAuth error: {token_data['error_description']}")

    access_token = token_data.get('access_token')
    if not access_token:
        raise RuntimeError("No access token received from GitHub")

    # Step 2: Fetch user info
    user_resp = requests.get(
        f"{GITHUB_API_URL}/user",
        headers={
            'Authorization': f'token {access_token}',
            'Accept': 'application/vnd.github.v3+json',
        },
        timeout=30
    )
    user_resp.raise_for_status()
    user_data = user_resp.json()

    return {
        'login': user_data.get('login'),
        'created_at': user_data.get('created_at'),
        'id': user_data.get('id'),
    }


def is_github_veteran(created_at: str) -> bool:
    """Check if GitHub account is older than 1 year."""
    if not created_at:
        return False
    try:
        created = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - created) > timedelta(days=365)
    except (ValueError, TypeError):
        return False


# =============================================================================
# Rate Limiting
# =============================================================================

def get_client_ip() -> str:
    """Get client IP safely."""
    forwarded = request.headers.get('X-Forwarded-For')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.remote_addr or '127.0.0.1'


def check_rate_limit(ip_address: str, github_username: str = None) -> tuple:
    """
    Check rate limit and return (allowed: bool, limit: float, next_time: str).
    GitHub auth increases limits. Veterans get the highest limit.
    """
    now = datetime.now(timezone.utc)

    # Determine limit tier
    if github_username:
        last_time, _ = get_last_drip_info(github_username, is_github=True)
        # Also check IP as secondary rate limit
        ip_time, _ = get_last_drip_info(ip_address, is_github=False)

        # Use the most restrictive of the two if both have recent drips
        if ip_time and last_time:
            ip_hours = (now - ip_time).total_seconds() / 3600
            gh_hours = (now - last_time).total_seconds() / 3600
            if ip_hours < RATE_LIMIT_HOURS and gh_hours >= RATE_LIMIT_HOURS:
                next_avail = ip_time + timedelta(hours=RATE_LIMIT_HOURS)
                return False, 0, next_avail.isoformat()
        elif ip_time:
            ip_hours = (now - ip_time).total_seconds() / 3600
            if ip_hours < RATE_LIMIT_HOURS:
                next_avail = ip_time + timedelta(hours=RATE_LIMIT_HOURS)
                return False, 0, next_avail.isoformat()

        # Check if veteran
        conn = get_db()
        c = conn.cursor()
        c.execute('''
            SELECT github_account_created_at FROM drip_requests
            WHERE github_username = ?
            ORDER BY timestamp DESC
            LIMIT 1
        ''', (github_username,))
        row = c.fetchone()
        conn.close()

        if row and row[0] and is_github_veteran(row[0]):
            limit = RATE_LIMITS['github_veteran']
        else:
            limit = RATE_LIMITS['github_auth']
    else:
        # IP-only rate limit
        last_time, _ = get_last_drip_info(ip_address, is_github=False)
        if last_time:
            hours_since = (now - last_time).total_seconds() / 3600
            if hours_since < RATE_LIMIT_HOURS:
                next_avail = last_time + timedelta(hours=RATE_LIMIT_HOURS)
                return False, 0, next_avail.isoformat()
        limit = RATE_LIMITS['ip_only']

    return True, limit, None


# =============================================================================
# Validation
# =============================================================================

def is_valid_wallet(wallet: str) -> bool:
    """Validate wallet address format."""
    if not wallet or len(wallet) < 10:
        return False
    return bool(RTC_WALLET_RE.fullmatch(wallet))


# =============================================================================
# Routes
# =============================================================================

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>RustChain Testnet Faucet</title>
    <style>
        * { box-sizing: border-box; }
        body {
            font-family: 'Courier New', monospace;
            max-width: 700px;
            margin: 40px auto;
            padding: 20px;
            background: #0a0a0a;
            color: #00ff00;
            line-height: 1.6;
        }
        h1 {
            color: #00ff00;
            border-bottom: 2px solid #00ff00;
            padding-bottom: 10px;
            text-align: center;
        }
        .auth-bar {
            text-align: right;
            margin-bottom: 15px;
            font-size: 14px;
        }
        .auth-bar a {
            color: #00ff00;
            text-decoration: underline;
        }
        .limits {
            background: #1a1a1a;
            border: 1px solid #333;
            padding: 15px;
            margin: 15px 0;
            border-radius: 5px;
            font-size: 14px;
        }
        .limits table {
            width: 100%;
            border-collapse: collapse;
        }
        .limits th, .limits td {
            padding: 8px;
            text-align: left;
            border-bottom: 1px solid #333;
        }
        .limits th {
            color: #00cc00;
        }
        .form-section {
            background: #1a1a1a;
            border: 1px solid #00ff00;
            padding: 25px;
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
        }
        button, .btn {
            display: inline-block;
            padding: 12px 24px;
            background: #00aa00;
            color: #000;
            border: none;
            border-radius: 3px;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
            text-decoration: none;
            transition: all 0.3s;
        }
        button:hover, .btn:hover { background: #00ff00; }
        button:disabled {
            background: #333;
            color: #666;
            cursor: not-allowed;
        }
        .github-btn {
            background: #24292e;
            color: #fff;
            border: 1px solid #444;
        }
        .github-btn:hover { background: #444; }
        .result {
            padding: 15px;
            margin: 15px 0;
            border-radius: 5px;
            font-weight: bold;
        }
        .success { background: #002200; border: 1px solid #00ff00; color: #00ff00; }
        .error { background: #220000; border: 1px solid #ff0000; color: #ff0000; }
        .info { background: #001122; border: 1px solid #0088ff; color: #0088ff; }
        .footer {
            text-align: center;
            margin-top: 30px;
            font-size: 12px;
            color: #555;
        }
        code {
            background: #111;
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 14px;
        }
    </style>
</head>
<body>
    <h1>🚰 RustChain Testnet Faucet</h1>

    <div class="auth-bar">
        {% if github_user %}
            ✅ Logged in as <strong>{{ github_user }}</strong>
            {% if is_veteran %}(Veteran: 2.0 RTC/24h){% else %}(Standard: 1.0 RTC/24h){% endif %}
            | <a href="/faucet?logout=1">Logout</a>
        {% else %}
            🔓 Anonymous (0.5 RTC/24h)
            | <a href="/faucet/oauth/start" class="btn github-btn">🔗 Login with GitHub</a>
        {% endif %}
    </div>

    <div class="limits">
        <table>
            <tr><th>Auth Level</th><th>Rate Limit</th><th>Requirements</th></tr>
            <tr><td>🔓 Anonymous</td><td>0.5 RTC / 24h</td><td>None</td></tr>
            <tr><td>✅ GitHub Auth</td><td>1.0 RTC / 24h</td><td>GitHub account</td></tr>
            <tr><td>⭐ GitHub Veteran</td><td>2.0 RTC / 24h</td><td>Account > 1 year old</td></tr>
        </table>
    </div>

    <div class="form-section">
        <h3>Request Test RTC</h3>
        <form method="POST" action="/faucet/drip">
            <label>Wallet Address:</label>
            <input type="text" name="wallet" placeholder="RTC... or 0x..." required>

            {% if github_user %}
                <input type="hidden" name="github_user" value="{{ github_user }}">
            {% endif %}

            <button type="submit" {% if not can_drip %}disabled{% endif %}>
                {% if can_drip %}💧 Request Drip{% else %}⏳ Wait until {{ next_available }}{% endif %}
            </button>
        </form>
    </div>

    {% if result %}
    <div class="result {{ result_type }}">
        {{ result }}
    </div>
    {% endif %}

    <div class="form-section">
        <h3>📡 API Usage</h3>
        <p>Programmatic access:</p>
        <code>curl -X POST {{ request_url_root }}faucet/drip \
  -H "Content-Type: application/json" \
  -d '{"wallet":"RTC..."}'</code>
        <p style="margin-top:10px">With GitHub auth (increases limit):</p>
        <code>curl -X POST {{ request_url_root }}faucet/drip \
  -H "Content-Type: application/json" \
  -H "X-GitHub-User: yourgithub" \
  -d '{"wallet":"RTC..."}'</code>
    </div>

    <div class="footer">
        RustChain Testnet Faucet | Bounty #751 Implementation<br>
        <a href="https://github.com/Scottcjn/rustchain-bounties/issues/751" style="color:#555">View Bounty</a>
    </div>
</body>
</html>
"""


@app.route('/faucet', methods=['GET'])
def faucet_ui():
    """Render faucet web UI."""
    # Handle logout
    if request.args.get('logout'):
        session.pop('github_user', None)
        session.pop('github_created_at', None)
        return redirect('/faucet')

    github_user = session.get('github_user')
    github_created_at = session.get('github_created_at')
    is_veteran = is_github_veteran(github_created_at) if github_created_at else False

    ip_address = get_client_ip()
    can_drip, limit, next_available = check_rate_limit(ip_address, github_user)

    # Check for result message in query params (from redirect)
    result = request.args.get('result')
    result_type = request.args.get('result_type', 'info')

    return render_template_string(
        HTML_TEMPLATE,
        github_user=github_user,
        is_veteran=is_veteran,
        can_drip=can_drip,
        next_available=next_available or 'N/A',
        result=result,
        result_type=result_type,
        request_url_root=request.url_root
    )


@app.route('/faucet/oauth/start', methods=['GET'])
def oauth_start():
    """Initiate GitHub OAuth flow."""
    if not GITHUB_CLIENT_ID:
        return jsonify({'ok': False, 'error': 'GitHub OAuth not configured'}), 500

    state = secrets.token_urlsafe(32)
    ip_address = get_client_ip()
    save_oauth_state(state, ip_address)

    return redirect(github_oauth_url(state))


@app.route('/faucet/oauth/callback', methods=['GET'])
def oauth_callback():
    """Handle GitHub OAuth callback."""
    code = request.args.get('code')
    state = request.args.get('state')
    ip_address = get_client_ip()

    if not code or not state:
        return redirect('/faucet?result=OAuth+failed:+missing+code+or+state&result_type=error')

    # Verify state for CSRF protection
    if not verify_oauth_state(state, ip_address):
        return redirect('/faucet?result=OAuth+failed:+invalid+or+expired+state&result_type=error')

    try:
        user_info = exchange_github_code(code)
        session['github_user'] = user_info['login']
        session['github_created_at'] = user_info.get('created_at', '')

        vet_status = "Veteran" if is_github_veteran(session['github_created_at']) else "Standard"
        return redirect(
            f'/faucet?result=Welcome,+{user_info["login"]}!+({vet_status}+rate+limit)&result_type=success'
        )
    except Exception as e:
        return redirect(f'/faucet?result=OAuth+error:+{urllib.parse.quote(str(e))}&result_type=error')


@app.route('/faucet/drip', methods=['POST'])
def faucet_drip():
    """Handle token drip request."""
    # Support both JSON and form data
    if request.is_json:
        data = request.get_json()
        wallet = (data.get('wallet') or '').strip()
        github_user = data.get('github_user', '') or session.get('github_user', '')
    else:
        wallet = (request.form.get('wallet') or '').strip()
        github_user = request.form.get('github_user', '') or session.get('github_user', '')

    # Validate wallet
    if not is_valid_wallet(wallet):
        return jsonify({
            'ok': False,
            'error': 'Invalid wallet address. Must be RTC + 40 hex chars or 0x + 40 hex chars.'
        }), 400

    ip_address = get_client_ip()

    # Check rate limit
    can_drip, limit, next_available = check_rate_limit(ip_address, github_user or None)
    if not can_drip:
        return jsonify({
            'ok': False,
            'error': 'Rate limit exceeded',
            'next_available': next_available,
            'limit': limit,
        }), 429

    # Record the drip (mock mode — no actual transfer for testnet)
    github_created_at = None
    if github_user:
        github_created_at = session.get('github_created_at', '')

    record_drip(wallet, ip_address, limit, github_user or None, github_created_at)

    # Return appropriate limit info
    vet_info = ""
    if github_user:
        vet_info = " (Veteran rate)" if is_github_veteran(github_created_at) else " (Standard GitHub rate)"

    return jsonify({
        'ok': True,
        'amount': limit,
        'wallet': wallet,
        'limit': limit,
        'limit_type': 'github_veteran' if (github_user and is_github_veteran(github_created_at)) else (
            'github_auth' if github_user else 'ip_only'
        ),
        'message': f'Dripped {limit} test RTC to {wallet}{vet_info}',
        'next_available': (datetime.now(timezone.utc) + timedelta(hours=RATE_LIMIT_HOURS)).isoformat(),
    })


@app.route('/faucet/status', methods=['GET'])
def faucet_status():
    """Check current rate limit status."""
    ip_address = get_client_ip()
    github_user = session.get('github_user')

    can_drip, limit, next_available = check_rate_limit(ip_address, github_user)

    last_ip_time, _ = get_last_drip_info(ip_address, is_github=False)
    last_gh_time, _ = get_last_drip_info(github_user, is_github=True) if github_user else (None, None)

    return jsonify({
        'ok': True,
        'ip_address': ip_address,
        'github_user': github_user,
        'can_drip': can_drip,
        'current_limit': limit,
        'limit_type': 'github_veteran' if (github_user and is_github_veteran(session.get('github_created_at', ''))) else (
            'github_auth' if github_user else 'ip_only'
        ),
        'next_available': next_available,
        'last_drip_ip': last_ip_time.isoformat() if last_ip_time else None,
        'last_drip_github': last_gh_time.isoformat() if last_gh_time else None,
    })


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({'ok': True, 'service': 'faucet', 'timestamp': datetime.now(timezone.utc).isoformat()})


# =============================================================================
# Main
# =============================================================================

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('FAUCET_PORT', 8090))
    debug = os.environ.get('FAUCET_DEBUG', '0') == '1'
    app.run(host='0.0.0.0', port=port, debug=debug)
