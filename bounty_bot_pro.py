# SPDX-License-Identifier: MIT

import sqlite3
import requests
import json
import hashlib
import time
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string
import google.generativeai as genai
import os
import re

DB_PATH = 'bounty_bot_pro.db'

app = Flask(__name__)

# Configuration
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
RUSTCHAIN_NODE_URL = os.getenv('RUSTCHAIN_NODE_URL', 'http://localhost:3030')
STAR_THRESHOLD = int(os.getenv('STAR_THRESHOLD', '1000'))

# Initialize Gemini
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-pro')

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wallet_address TEXT NOT NULL,
                content_url TEXT NOT NULL,
                content_type TEXT NOT NULL,
                ai_score_technical INTEGER DEFAULT 0,
                ai_score_clarity INTEGER DEFAULT 0,
                ai_score_originality INTEGER DEFAULT 0,
                total_score INTEGER DEFAULT 0,
                star_king_bonus REAL DEFAULT 0.0,
                wallet_balance INTEGER DEFAULT 0,
                verification_status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processed_at TIMESTAMP NULL,
                error_message TEXT NULL
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS star_kings (
                wallet_address TEXT PRIMARY KEY,
                star_count INTEGER NOT NULL,
                verified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                bonus_multiplier REAL NOT NULL
            )
        ''')
        conn.commit()

def verify_wallet_with_node(wallet_address):
    try:
        response = requests.get(f'{RUSTCHAIN_NODE_URL}/wallet/balance/{wallet_address}',
                              timeout=10)
        if response.status_code == 200:
            data = response.json()
            return True, data.get('balance', 0)
        return False, 0
    except Exception as e:
        print(f"Node verification failed: {e}")
        return False, 0

def extract_content_from_url(url):
    try:
        headers = {'User-Agent': 'RustChain-BountyBot-Pro/1.0'}
        response = requests.get(url, headers=headers, timeout=15)

        if response.status_code == 200:
            content = response.text

            # Basic content extraction (could be enhanced with BeautifulSoup)
            text_content = re.sub(r'<[^>]+>', ' ', content)
            text_content = re.sub(r'\s+', ' ', text_content).strip()

            return text_content[:5000]  # Limit to first 5000 chars
        return None
    except Exception as e:
        print(f"Content extraction failed: {e}")
        return None

def analyze_content_with_ai(content):
    if not GEMINI_API_KEY or not content:
        return 5, 5, 5  # Default scores

    try:
        prompt = f"""
        Analyze this RustChain-related content and provide scores from 0-10 for:
        1. Technical Depth: How technically detailed and accurate is the content?
        2. Clarity: How well-written and easy to understand is it?
        3. Originality: How original and unique is the content?

        Content to analyze:
        {content}

        Respond ONLY with three numbers separated by commas (e.g., "7,8,6").
        """

        response = model.generate_content(prompt)
        scores_text = response.text.strip()

        scores = [int(x.strip()) for x in scores_text.split(',')]
        if len(scores) == 3:
            return tuple(max(0, min(10, score)) for score in scores)

    except Exception as e:
        print(f"AI analysis failed: {e}")

    return 5, 5, 5

def detect_star_king(wallet_address):
    try:
        # Check GitHub stars for RustChain repos associated with this wallet
        # This is a simplified implementation
        response = requests.get(f'{RUSTCHAIN_NODE_URL}/wallet/metadata/{wallet_address}',
                              timeout=10)

        if response.status_code == 200:
            metadata = response.json()
            github_username = metadata.get('github_username')

            if github_username:
                # Query GitHub API for stars
                github_response = requests.get(f'https://api.github.com/users/{github_username}/starred',
                                             timeout=10)
                if github_response.status_code == 200:
                    starred_repos = github_response.json()
                    rustchain_stars = sum(1 for repo in starred_repos
                                        if 'rustchain' in repo.get('name', '').lower())

                    if rustchain_stars >= STAR_THRESHOLD:
                        bonus = min(2.0, 1.0 + (rustchain_stars - STAR_THRESHOLD) * 0.001)

                        with sqlite3.connect(DB_PATH) as conn:
                            cursor = conn.cursor()
                            cursor.execute('''
                                INSERT OR REPLACE INTO star_kings
                                (wallet_address, star_count, bonus_multiplier)
                                VALUES (?, ?, ?)
                            ''', (wallet_address, rustchain_stars, bonus))
                            conn.commit()

                        return bonus

        return 1.0
    except Exception as e:
        print(f"Star King detection failed: {e}")
        return 1.0

@app.route('/')
def index():
    return render_template_string('''
    <html>
    <head><title>Bounty Bot PRO</title></head>
    <body>
        <h1>RustChain Bounty Bot PRO</h1>
        <h2>Submit Content for Verification</h2>
        <form action="/submit" method="post">
            <p>Wallet Address: <input type="text" name="wallet" required style="width:400px"></p>
            <p>Content URL: <input type="url" name="url" required style="width:400px"></p>
            <p>Content Type:
                <select name="type">
                    <option value="article">Technical Article</option>
                    <option value="tutorial">Tutorial</option>
                    <option value="documentation">Documentation</option>
                    <option value="analysis">Analysis</option>
                </select>
            </p>
            <p><input type="submit" value="Submit for Verification"></p>
        </form>

        <h2>Recent Submissions</h2>
        <div id="submissions">
            <!-- Will be populated via AJAX -->
        </div>

        <script>
            fetch('/submissions')
                .then(r => r.json())
                .then(data => {
                    let html = '<table border="1"><tr><th>Wallet</th><th>URL</th><th>AI Scores</th><th>Status</th><th>Star Bonus</th></tr>';
                    data.forEach(sub => {
                        html += `<tr><td>${sub.wallet_address.substring(0,10)}...</td><td><a href="${sub.content_url}">Link</a></td><td>T:${sub.ai_score_technical} C:${sub.ai_score_clarity} O:${sub.ai_score_originality}</td><td>${sub.verification_status}</td><td>${sub.star_king_bonus}x</td></tr>`;
                    });
                    html += '</table>';
                    document.getElementById('submissions').innerHTML = html;
                });
        </script>
    </body>
    </html>
    ''')

@app.route('/submit', methods=['POST'])
def submit_bounty():
    wallet_address = request.form.get('wallet', '').strip()
    content_url = request.form.get('url', '').strip()
    content_type = request.form.get('type', 'article')

    if not wallet_address or not content_url:
        return jsonify({'error': 'Missing required fields'}), 400

    # Verify wallet with RustChain node
    wallet_valid, balance = verify_wallet_with_node(wallet_address)
    if not wallet_valid:
        return jsonify({'error': 'Invalid wallet address or node unreachable'}), 400

    # Extract content from URL
    content = extract_content_from_url(content_url)
    if not content:
        return jsonify({'error': 'Could not extract content from URL'}), 400

    # AI analysis
    tech_score, clarity_score, orig_score = analyze_content_with_ai(content)
    total_score = tech_score + clarity_score + orig_score

    # Star King detection
    star_bonus = detect_star_king(wallet_address)

    # Store submission
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO submissions
            (wallet_address, content_url, content_type, ai_score_technical,
             ai_score_clarity, ai_score_originality, total_score, star_king_bonus,
             wallet_balance, verification_status, processed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (wallet_address, content_url, content_type, tech_score, clarity_score,
              orig_score, total_score, star_bonus, balance, 'verified',
              datetime.now().isoformat()))
        conn.commit()

    return jsonify({
        'status': 'verified',
        'scores': {
            'technical': tech_score,
            'clarity': clarity_score,
            'originality': orig_score,
            'total': total_score
        },
        'star_king_bonus': star_bonus,
        'wallet_balance': balance
    })

@app.route('/submissions')
def get_submissions():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT wallet_address, content_url, ai_score_technical, ai_score_clarity,
                   ai_score_originality, verification_status, star_king_bonus
            FROM submissions
            ORDER BY created_at DESC
            LIMIT 20
        ''')

        submissions = []
        for row in cursor.fetchall():
            submissions.append({
                'wallet_address': row[0],
                'content_url': row[1],
                'ai_score_technical': row[2],
                'ai_score_clarity': row[3],
                'ai_score_originality': row[4],
                'verification_status': row[5],
                'star_king_bonus': row[6]
            })

    return jsonify(submissions)

@app.route('/star-kings')
def get_star_kings():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM star_kings ORDER BY star_count DESC')

        star_kings = []
        for row in cursor.fetchall():
            star_kings.append({
                'wallet_address': row[0],
                'star_count': row[1],
                'verified_at': row[2],
                'bonus_multiplier': row[3]
            })

    return jsonify(star_kings)

@app.route('/health')
def health_check():
    try:
        # Check database connection
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM submissions')
            submission_count = cursor.fetchone()[0]

        # Check node connectivity
        node_status = 'offline'
        try:
            response = requests.get(f'{RUSTCHAIN_NODE_URL}/health', timeout=5)
            if response.status_code == 200:
                node_status = 'online'
        except:
            pass

        return jsonify({
            'status': 'healthy',
            'database': 'connected',
            'submissions_count': submission_count,
            'node_status': node_status,
            'ai_enabled': bool(GEMINI_API_KEY),
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5001)
