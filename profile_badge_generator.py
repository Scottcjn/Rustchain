#/ SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

from flask import Flask, request, jsonify, render_template_string
import sqlite3
import json
import urllib.parse
import hashlib
from datetime import datetime

app = Flask(__name__)

DB_PATH = "rustchain.db"

def init_badge_db():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS profile_badges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                github_username TEXT NOT NULL,
                wallet_address TEXT,
                badge_type TEXT DEFAULT 'contributor',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                bounty_earned DECIMAL(10,2) DEFAULT 0.0,
                custom_message TEXT
            )
        ''')
        conn.commit()

@app.route('/badge/generator')
def badge_generator():
    html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>RustChain Badge Generator</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
            .form-group { margin-bottom: 15px; }
            label { display: block; margin-bottom: 5px; font-weight: bold; }
            input, select, textarea { width: 100%; padding: 8px; box-sizing: border-box; }
            button { background: #007cba; color: white; padding: 10px 20px; border: none; cursor: pointer; }
            .badge-preview { background: #f5f5f5; padding: 20px; margin: 20px 0; border-radius: 5px; }
            .code-block { background: #2d2d2d; color: #f8f8f2; padding: 15px; margin: 10px 0; overflow-x: auto; }
        </style>
    </head>
    <body>
        <h1>RustChain Profile Badge Generator</h1>
        <form id="badgeForm">
            <div class="form-group">
                <label for="username">GitHub Username:</label>
                <input type="text" id="username" name="username" required>
            </div>
            <div class="form-group">
                <label for="wallet">Wallet Address (Optional):</label>
                <input type="text" id="wallet" name="wallet">
            </div>
            <div class="form-group">
                <label for="badgeType">Badge Type:</label>
                <select id="badgeType" name="badgeType">
                    <option value="contributor">Contributor</option>
                    <option value="bounty-hunter">Bounty Hunter</option>
                    <option value="developer">Developer</option>
                    <option value="supporter">Supporter</option>
                </select>
            </div>
            <div class="form-group">
                <label for="customMessage">Custom Message (Optional):</label>
                <input type="text" id="customMessage" name="customMessage" placeholder="e.g., Active Contributor">
            </div>
            <button type="button" onclick="generateBadge()">Generate Badge</button>
        </form>
        
        <div id="result" style="display:none;">
            <h2>Your RustChain Badge</h2>
            <div class="badge-preview">
                <h3>Preview:</h3>
                <div id="badgePreview"></div>
            </div>
            <h3>Markdown for GitHub README:</h3>
            <div class="code-block" id="markdownCode"></div>
            <h3>HTML Version:</h3>
            <div class="code-block" id="htmlCode"></div>
        </div>

        <script>
        function generateBadge() {
            const username = document.getElementById('username').value;
            const wallet = document.getElementById('wallet').value;
            const badgeType = document.getElementById('badgeType').value;
            const customMessage = document.getElementById('customMessage').value;
            
            if (!username) {
                alert('Please enter your GitHub username');
                return;
            }
            
            fetch('/api/badge/create', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    username: username,
                    wallet: wallet,
                    badge_type: badgeType,
                    custom_message: customMessage
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    document.getElementById('badgePreview').innerHTML = data.preview_html;
                    document.getElementById('markdownCode').textContent = data.markdown;
                    document.getElementById('htmlCode').textContent = data.html;
                    document.getElementById('result').style.display = 'block';
                }
            })
            .catch(error => console.error('Error:', error));
        }
        </script>
    </body>
    </html>
    '''
    return render_template_string(html)

@app.route('/api/badge/create', methods=['POST'])
def create_badge():
    init_badge_db()
    data = request.get_json()
    
    username = data.get('username', '').strip()
    wallet = data.get('wallet', '').strip()
    badge_type = data.get('badge_type', 'contributor')
    custom_message = data.get('custom_message', '').strip()
    
    if not username:
        return jsonify({'success': False, 'error': 'Username required'})
    
    badge_colors = {
        'contributor': 'blue',
        'bounty-hunter': 'green',
        'developer': 'orange',
        'supporter': 'purple'
    }
    
    color = badge_colors.get(badge_type, 'blue')
    label = custom_message if custom_message else badge_type.replace('-', ' ').title()
    
    shield_url = f"https://img.shields.io/badge/RustChain-{urllib.parse.quote(label)}-{color}"
    repo_url = "https://github.com/Scottcjn/Rustchain"
    
    markdown = f"[![RustChain {label}]({shield_url})]({repo_url})"
    html = f'<a href="{repo_url}"><img src="{shield_url}" alt="RustChain {label}"></a>'
    preview_html = f'<img src="{shield_url}" alt="RustChain {label}">'
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO profile_badges 
            (github_username, wallet_address, badge_type, custom_message, bounty_earned)
            VALUES (?, ?, ?, ?, ?)
        ''', (username, wallet or None, badge_type, custom_message or None, 3.0))
        conn.commit()
    
    return jsonify({
        'success': True,
        'markdown': markdown,
        'html': html,
        'preview_html': preview_html,
        'shield_url': shield_url
    })

@app.route('/api/badge/stats')
def badge_stats():
    init_badge_db()
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) as total FROM profile_badges')
        total = cursor.fetchone()[0]
        
        cursor.execute('SELECT badge_type, COUNT(*) as count FROM profile_badges GROUP BY badge_type')
        type_stats = dict(cursor.fetchall())
        
        cursor.execute('SELECT SUM(bounty_earned) as total_bounties FROM profile_badges')
        total_bounties = cursor.fetchone()[0] or 0
    
    return jsonify({
        'total_badges': total,
        'badge_types': type_stats,
        'total_bounties_earned': float(total_bounties)
    })

@app.route('/api/badge/list')
def list_badges():
    init_badge_db()
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT github_username, badge_type, custom_message, created_at, bounty_earned
            FROM profile_badges 
            ORDER BY created_at DESC
        ''')
        badges = cursor.fetchall()
    
    badge_list = []
    for badge in badges:
        badge_list.append({
            'username': badge[0],
            'type': badge[1],
            'custom_message': badge[2],
            'created': badge[3],
            'bounty': float(badge[4]) if badge[4] else 0.0
        })
    
    return jsonify({'badges': badge_list})

if __name__ == '__main__':
    init_badge_db()
    app.run(debug=True, port=5003)