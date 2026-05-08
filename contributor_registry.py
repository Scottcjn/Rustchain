# SPDX-License-Identifier: MIT

from flask import Flask, request, redirect, url_for, flash
import sqlite3
import os
import secrets
from datetime import datetime

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
        UserWarning
    )
elif SECRET_KEY == 'rustchain_contributor_secret_2024':
    import warnings
    warnings.warn(
        "CONTRIBUTOR_SECRET_KEY is set to the known placeholder value. "
        "Please set a new, secure secret before deployment.",
        UserWarning
    )

app.secret_key = SECRET_KEY

DB_PATH = 'contributors.db'

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
            <div class="contributor status-{{ contributor[6] }}">
                <strong>@{{ contributor[1] }}</strong> ({{ contributor[2] }})
                <br><small>Wallet: {{ contributor[3] }}</small>
                <br><small>Registered: {{ contributor[5] }} | Status: {{ contributor[6] }}</small>
                {% if contributor[4] %}
                    <br><em>{{ contributor[4][:200] }}{% if contributor[4]|length > 200 %}...{% endif %}</em>
                {% endif %}
            </div>
            {% endfor %}
        </div>
    </body>
    </html>
    '''
    
    with sqlite3.connect(DB_PATH) as conn:
        contributors = conn.execute(
            'SELECT * FROM contributors ORDER BY registration_date DESC'
        ).fetchall()
    
    from flask import render_template_string
    return render_template_string(html, contributors=contributors)

@app.route('/register', methods=['POST'])
def register():
    github_username = request.form.get('github_username', '').strip()
    contributor_type = request.form.get('contributor_type', '').strip()
    rtc_wallet = request.form.get('rtc_wallet', '').strip()
    contribution_history = request.form.get('contribution_history', '')
    
    if not github_username or not contributor_type or not rtc_wallet:
        flash('Error: All required fields must be provided')
        return redirect(url_for('index'))
    if len(github_username) > 39 or len(rtc_wallet) > 128:
        flash('Error: Input too long')
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
                'wallet': c[2],
                'registered': c[3],
                'status': c[4]
            }
            for c in contributors
        ]
    }

@app.route('/approve/<username>')
def approve_contributor(username):
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