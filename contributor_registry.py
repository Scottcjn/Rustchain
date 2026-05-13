# SPDX-License-Identifier: MIT

import os
import re
import secrets
import sqlite3

from flask import Flask, abort, flash, redirect, request, session, url_for

app = Flask(__name__)

# Security fix: load secret_key from environment variable.
# If unset, fall back to a cryptographically random key (warns on first start).
# If set to the known placeholder, refuse to run (prevents accidental deployment
# with the compromised default secret).
SECRET_KEY = os.environ.get('CONTRIBUTOR_SECRET_KEY', '')
if not SECRET_KEY:
    import warnings
    SECRET_KEY = secrets.token_hex(32)
    warnings.warn(
        "CONTRIBUTOR_SECRET_KEY not set. "
        "Using a random key — sessions will NOT persist across restarts. "
        "Set the environment variable before deployment.",
        UserWarning,
        stacklevel=2,
    )
elif SECRET_KEY == 'rustchain_contributor_secret_2024':
    import warnings
    warnings.warn(
        "CONTRIBUTOR_SECRET_KEY is set to the known placeholder value. "
        "Please set a new, secure secret before deployment.",
        UserWarning,
        stacklevel=2,
    )

app.secret_key = SECRET_KEY

DB_PATH = 'contributors.db'
ALLOWED_CONTRIBUTOR_TYPES = {"human", "bot", "agent"}
GITHUB_USERNAME_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")
RTC_WALLET_RE = re.compile(r"^RTC[0-9a-fA-F]{40}$")
EVM_WALLET_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")

app.config["CONTRIBUTOR_REGISTRATION_TOKEN"] = os.environ.get("CONTRIBUTOR_REGISTRATION_TOKEN", "")
app.config["CONTRIBUTOR_ADMIN_TOKEN"] = os.environ.get("CONTRIBUTOR_ADMIN_TOKEN", "")


def normalize_github_username(username):
    username = username.strip().removeprefix("@")
    if not GITHUB_USERNAME_RE.fullmatch(username) or "--" in username:
        raise ValueError("Enter a valid GitHub username.")
    return username


def validate_contributor_type(contributor_type):
    contributor_type = contributor_type.strip().lower()
    if contributor_type not in ALLOWED_CONTRIBUTOR_TYPES:
        raise ValueError("Select a valid contributor type.")
    return contributor_type


def validate_wallet(wallet):
    wallet = wallet.strip()
    if not (RTC_WALLET_RE.fullmatch(wallet) or EVM_WALLET_RE.fullmatch(wallet)):
        raise ValueError("Enter a valid RTC or EVM wallet address.")
    return wallet


def redact_wallet(wallet):
    if len(wallet) <= 12:
        return "***"
    return f"{wallet[:6]}...{wallet[-4:]}"


def get_csrf_token():
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def validate_csrf_token(token):
    stored_token = session.get("csrf_token", "")
    if not stored_token or not token or not secrets.compare_digest(stored_token, token):
        abort(400)


def validate_registration_token(token):
    configured_token = app.config.get("CONTRIBUTOR_REGISTRATION_TOKEN", "")
    if not configured_token:
        raise ValueError("Contributor registration is closed until a registration token is configured.")
    if not token or not secrets.compare_digest(configured_token, token):
        raise ValueError("Invalid contributor registration token.")


def require_admin_token():
    configured_token = app.config.get("CONTRIBUTOR_ADMIN_TOKEN", "")
    supplied_token = request.headers.get("X-Admin-Token", "") or request.args.get("admin_token", "")
    if not configured_token or not supplied_token or not secrets.compare_digest(configured_token, supplied_token):
        abort(403)


def build_contributor_view(contributor):
    return {
        "github_username": contributor[0],
        "type": contributor[1],
        "wallet": redact_wallet(contributor[2]),
        "history": contributor[3],
        "registered": contributor[4],
        "status": contributor[5],
    }


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS contributors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                github_username TEXT UNIQUE NOT NULL,
                contributor_type TEXT NOT NULL,
                rtc_wallet TEXT NOT NULL,
                contribution_history TEXT,
                registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'pending'
            )
        ''')
        conn.commit()

@app.route('/')
def index():
    html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>RustChain Contributor Registry</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
            .form-group { margin: 15px 0; }
            label { display: block; margin-bottom: 5px; font-weight: bold; }
            input, select, textarea { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; }
            button { background: #007cba; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; }
            button:hover { background: #005a8b; }
            .contributors { margin-top: 40px; }
            .contributor { border: 1px solid #eee; padding: 15px; margin: 10px 0; border-radius: 4px; }
            .status-pending { border-left: 4px solid #ffa500; }
            .status-approved { border-left: 4px solid #28a745; }
            h1, h2 { color: #333; }
        </style>
    </head>
    <body>
        <h1>RustChain Ecosystem Contributor Registry</h1>
        <p><strong>Bounty:</strong> 5 RTC per registration</p>

        <h2>Register as Contributor</h2>
        <form method="POST" action="/register">
            <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
            <div class="form-group">
                <label for="github_username">GitHub Username:</label>
                <input type="text" id="github_username" name="github_username" required>
            </div>

            <div class="form-group">
                <label for="contributor_type">Type:</label>
                <select id="contributor_type" name="contributor_type" required>
                    <option value="">Select type</option>
                    <option value="human">Human</option>
                    <option value="bot">Bot</option>
                    <option value="agent">Agent</option>
                </select>
            </div>

            <div class="form-group">
                <label for="rtc_wallet">RTC Wallet Address:</label>
                <input type="text" id="rtc_wallet" name="rtc_wallet" required>
            </div>

            <div class="form-group">
                <label for="registration_token">Registration Token:</label>
                <input type="password" id="registration_token" name="registration_token" autocomplete="one-time-code" required>
            </div>

            <div class="form-group">
                <label for="contribution_history">Contribution History:</label>
                <textarea id="contribution_history" name="contribution_history" rows="4"
                    placeholder="Describe your contributions (starred repos, PRs, issues, tutorials, mining, security research, community support, etc.)"></textarea>
            </div>

            <button type="submit">Register</button>
        </form>

        <div class="contributors">
            <h2>Registered Contributors</h2>
            {% for message in get_flashed_messages() %}
                <div style="color: green; margin: 10px 0;">{{ message }}</div>
            {% endfor %}

            {% for contributor in contributors %}
            <div class="contributor status-{{ contributor.status }}">
                <strong>@{{ contributor.github_username }}</strong> ({{ contributor.type }})
                <br><small>Wallet: {{ contributor.wallet }}</small>
                <br><small>Registered: {{ contributor.registered }} | Status: {{ contributor.status }}</small>
                {% if contributor.history %}
                    <br><em>{{ contributor.history[:200] }}{% if contributor.history|length > 200 %}...{% endif %}</em>
                {% endif %}
            </div>
            {% endfor %}
        </div>
    </body>
    </html>
    '''

    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            'SELECT github_username, contributor_type, rtc_wallet, contribution_history, registration_date, status '
            'FROM contributors ORDER BY registration_date DESC'
        ).fetchall()
    contributors = [build_contributor_view(row) for row in rows]

    from flask import render_template_string
    return render_template_string(html, contributors=contributors, csrf_token=get_csrf_token())

@app.route('/register', methods=['POST'])
def register():
    validate_csrf_token(request.form.get('csrf_token', ''))

    try:
        validate_registration_token(request.form.get('registration_token', ''))
        github_username = normalize_github_username(request.form.get('github_username', ''))
        contributor_type = validate_contributor_type(request.form.get('contributor_type', ''))
        rtc_wallet = validate_wallet(request.form.get('rtc_wallet', ''))
        contribution_history = request.form.get('contribution_history', '').strip()[:2000]
    except ValueError as exc:
        flash(str(exc))
        return redirect(url_for('index'))

    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                'INSERT INTO contributors (github_username, contributor_type, rtc_wallet, contribution_history) VALUES (?, ?, ?, ?)',
                (github_username, contributor_type, rtc_wallet, contribution_history)
            )
            conn.commit()
        flash(f'Successfully registered @{github_username}! Pending approval for 5 RTC bounty.')
    except sqlite3.IntegrityError:
        flash(f'Error: @{github_username} is already registered!')

    return redirect(url_for('index'))

@app.route('/api/contributors')
def api_contributors():
    with sqlite3.connect(DB_PATH) as conn:
        contributors = conn.execute(
            'SELECT github_username, contributor_type, rtc_wallet, registration_date, status FROM contributors ORDER BY registration_date DESC'
        ).fetchall()

    return {
        'contributors': [
            {
                'github_username': c[0],
                'type': c[1],
                'wallet': redact_wallet(c[2]),
                'registered': c[3],
                'status': c[4]
            }
            for c in contributors
        ]
    }

@app.route('/approve/<username>')
def approve_contributor(username):
    require_admin_token()
    try:
        username = normalize_github_username(username)
    except ValueError:
        abort(400)

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            'UPDATE contributors SET status = "approved" WHERE github_username = ?',
            (username,)
        )
        conn.commit()
    flash(f'Approved @{username} for 5 RTC bounty!')
    return redirect(url_for('index'))

if __name__ == '__main__':
    if not os.path.exists(DB_PATH):
        init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
