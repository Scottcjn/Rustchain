// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import os
import json
import sqlite3
import requests
import time
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string
import google.generativeai as genai
from urllib.parse import urlparse
import re

app = Flask(__name__)

# Configuration
DB_PATH = 'bounty_bot_pro.db'
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
RUSTCHAIN_NODE_URL = os.getenv('RUSTCHAIN_NODE_URL', 'http://localhost:8332')
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
STAR_KING_THRESHOLD = int(os.getenv('STAR_KING_THRESHOLD', '1000'))
QUALITY_THRESHOLD = float(os.getenv('QUALITY_THRESHOLD', '7.0'))

# Initialize Gemini
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-pro')

def init_database():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS quality_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content_hash TEXT UNIQUE,
                url TEXT,
                technical_depth REAL,
                clarity REAL,
                originality REAL,
                overall_score REAL,
                ai_feedback TEXT,
                scored_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.execute('''
            CREATE TABLE IF NOT EXISTS wallet_verifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wallet_address TEXT UNIQUE,
                balance REAL,
                is_valid BOOLEAN,
                last_checked TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.execute('''
            CREATE TABLE IF NOT EXISTS star_kings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                github_user TEXT UNIQUE,
                stars INTEGER,
                bonus_multiplier REAL,
                detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.execute('''
            CREATE TABLE IF NOT EXISTS bounty_submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                github_user TEXT,
                wallet_address TEXT,
                content_url TEXT,
                quality_score REAL,
                is_star_king BOOLEAN DEFAULT FALSE,
                bonus_multiplier REAL DEFAULT 1.0,
                status TEXT DEFAULT 'pending',
                submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

def analyze_content_quality(content_text, url):
    if not GEMINI_API_KEY or not content_text:
        return None
    
    try:
        prompt = f"""
        Analyze this technical content for a RustChain bounty submission:
        
        URL: {url}
        Content: {content_text[:3000]}
        
        Score on a scale of 0-10 for:
        1. Technical Depth - How technically sophisticated and detailed is the content?
        2. Clarity - How well-written and easy to understand is it?
        3. Originality - How original and unique is the contribution?
        
        Return ONLY a JSON object like:
        {{"technical_depth": 8.5, "clarity": 7.2, "originality": 9.1, "feedback": "Brief explanation"}}
        """
        
        response = model.generate_content(prompt)
        result = json.loads(response.text.strip())
        
        overall = (result['technical_depth'] + result['clarity'] + result['originality']) / 3
        result['overall_score'] = round(overall, 2)
        
        return result
        
    except Exception as e:
        print(f"AI scoring error: {e}")
        return None

def verify_wallet_with_node(wallet_address):
    try:
        response = requests.get(f"{RUSTCHAIN_NODE_URL}/wallet/balance/{wallet_address}", timeout=10)
        if response.status_code == 200:
            data = response.json()
            return {
                'is_valid': True,
                'balance': data.get('balance', 0.0)
            }
        return {'is_valid': False, 'balance': 0.0}
    except:
        return {'is_valid': False, 'balance': 0.0}

def check_star_king_status(github_user):
    if not GITHUB_TOKEN:
        return {'is_star_king': False, 'stars': 0, 'multiplier': 1.0}
    
    try:
        headers = {'Authorization': f'token {GITHUB_TOKEN}'}
        response = requests.get(f"https://api.github.com/users/{github_user}", headers=headers)
        
        if response.status_code == 200:
            user_data = response.json()
            total_stars = 0
            
            repos_response = requests.get(f"https://api.github.com/users/{github_user}/repos", headers=headers)
            if repos_response.status_code == 200:
                repos = repos_response.json()
                total_stars = sum(repo.get('stargazers_count', 0) for repo in repos)
            
            is_star_king = total_stars >= STAR_KING_THRESHOLD
            multiplier = 1.0 + (total_stars / STAR_KING_THRESHOLD) * 0.5 if is_star_king else 1.0
            
            return {
                'is_star_king': is_star_king,
                'stars': total_stars,
                'multiplier': round(multiplier, 2)
            }
    except:
        pass
    
    return {'is_star_king': False, 'stars': 0, 'multiplier': 1.0}

def fetch_url_content(url):
    try:
        response = requests.get(url, timeout=15, headers={'User-Agent': 'BountyBot-PRO/1.0'})
        if response.status_code == 200:
            return response.text[:5000]
    except:
        pass
    return ""

@app.route('/')
def dashboard():
    return render_template_string('''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Bounty Bot PRO Dashboard</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
            .container { max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            .header { text-align: center; margin-bottom: 30px; }
            .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }
            .stat-card { background: #2196F3; color: white; padding: 20px; border-radius: 6px; text-align: center; }
            .endpoint { background: #f8f9fa; padding: 15px; margin: 10px 0; border-radius: 4px; border-left: 4px solid #007bff; }
            .method { display: inline-block; padding: 4px 8px; border-radius: 3px; font-weight: bold; color: white; }
            .post { background-color: #28a745; }
            .get { background-color: #17a2b8; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🚀 Bounty Bot PRO</h1>
                <p>AI Quality Scoring & RustChain Node Integration</p>
            </div>
            
            <div class="stats">
                <div class="stat-card">
                    <h3>{{ stats.total_submissions }}</h3>
                    <p>Total Submissions</p>
                </div>
                <div class="stat-card">
                    <h3>{{ stats.star_kings }}</h3>
                    <p>Star Kings Detected</p>
                </div>
                <div class="stat-card">
                    <h3>{{ stats.avg_quality }}</h3>
                    <p>Average Quality Score</p>
                </div>
                <div class="stat-card">
                    <h3>{{ stats.verified_wallets }}</h3>
                    <p>Verified Wallets</p>
                </div>
            </div>
            
            <h2>API Endpoints</h2>
            
            <div class="endpoint">
                <span class="method post">POST</span>
                <strong>/api/score-content</strong>
                <p>AI-powered quality scoring for content submissions</p>
                <small>Body: {"url": "https://...", "content": "..."}</small>
            </div>
            
            <div class="endpoint">
                <span class="method post">POST</span>
                <strong>/api/verify-wallet</strong>
                <p>Verify wallet against RustChain node</p>
                <small>Body: {"wallet_address": "..."}</small>
            </div>
            
            <div class="endpoint">
                <span class="method get">GET</span>
                <strong>/api/check-star-king/{github_user}</strong>
                <p>Check if user qualifies as Star King</p>
            </div>
            
            <div class="endpoint">
                <span class="method post">POST</span>
                <strong>/api/submit-bounty</strong>
                <p>Complete bounty submission with full verification</p>
                <small>Body: {"github_user": "...", "wallet": "...", "content_url": "..."}</small>
            </div>
        </div>
    </body>
    </html>
    ''', stats=get_dashboard_stats())

def get_dashboard_stats():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM bounty_submissions")
        total_submissions = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM star_kings")
        star_kings = cursor.fetchone()[0]
        
        cursor.execute("SELECT AVG(quality_score) FROM bounty_submissions WHERE quality_score IS NOT NULL")
        avg_quality = cursor.fetchone()[0] or 0.0
        
        cursor.execute("SELECT COUNT(*) FROM wallet_verifications WHERE is_valid = 1")
        verified_wallets = cursor.fetchone()[0]
        
        return {
            'total_submissions': total_submissions,
            'star_kings': star_kings,
            'avg_quality': round(avg_quality, 2),
            'verified_wallets': verified_wallets
        }

@app.route('/api/score-content', methods=['POST'])
def score_content():
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({'error': 'URL required'}), 400
    
    url = data['url']
    content = data.get('content', '')
    
    if not content:
        content = fetch_url_content(url)
    
    content_hash = str(hash(content + url))
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM quality_scores WHERE content_hash = ?", (content_hash,))
        existing = cursor.fetchone()
        
        if existing:
            return jsonify({
                'cached': True,
                'technical_depth': existing[2],
                'clarity': existing[3],
                'originality': existing[4],
                'overall_score': existing[5],
                'feedback': existing[6]
            })
    
    quality_result = analyze_content_quality(content, url)
    
    if quality_result:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO quality_scores 
                (content_hash, url, technical_depth, clarity, originality, overall_score, ai_feedback)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                content_hash, url,
                quality_result['technical_depth'],
                quality_result['clarity'],
                quality_result['originality'],
                quality_result['overall_score'],
                quality_result['feedback']
            ))
        
        return jsonify(quality_result)
    
    return jsonify({'error': 'Content analysis failed'}), 500

@app.route('/api/verify-wallet', methods=['POST'])
def verify_wallet():
    data = request.get_json()
    if not data or 'wallet_address' not in data:
        return jsonify({'error': 'wallet_address required'}), 400
    
    wallet_address = data['wallet_address']
    verification_result = verify_wallet_with_node(wallet_address)
    
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            INSERT OR REPLACE INTO wallet_verifications 
            (wallet_address, balance, is_valid)
            VALUES (?, ?, ?)
        ''', (wallet_address, verification_result['balance'], verification_result['is_valid']))
    
    return jsonify(verification_result)

@app.route('/api/check-star-king/<github_user>')
def check_star_king(github_user):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM star_kings WHERE github_user = ?", (github_user,))
        cached = cursor.fetchone()
        
        if cached:
            return jsonify({
                'is_star_king': bool(cached[2] >= STAR_KING_THRESHOLD),
                'stars': cached[2],
                'multiplier': cached[3],
                'cached': True
            })
    
    star_result = check_star_king_status(github_user)
    
    if star_result['is_star_king']:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO star_kings 
                (github_user, stars, bonus_multiplier)
                VALUES (?, ?, ?)
            ''', (github_user, star_result['stars'], star_result['multiplier']))
    
    return jsonify(star_result)

@app.route('/api/submit-bounty', methods=['POST'])
def submit_bounty():
    data = request.get_json()
    required_fields = ['github_user', 'wallet_address', 'content_url']
    
    if not data or not all(field in data for field in required_fields):
        return jsonify({'error': 'Missing required fields'}), 400
    
    github_user = data['github_user']
    wallet_address = data['wallet_address']
    content_url = data['content_url']
    
    # Verify wallet
    wallet_result = verify_wallet_with_node(wallet_address)
    if not wallet_result['is_valid']:
        return jsonify({'error': 'Invalid wallet address'}), 400
    
    # Check content quality
    content = fetch_url_content(content_url)
    quality_result = analyze_content_quality(content, content_url)
    
    if not quality_result or quality_result['overall_score'] < QUALITY_THRESHOLD:
        return jsonify({
            'error': 'Content quality below threshold',
            'score': quality_result['overall_score'] if quality_result else 0,
            'threshold': QUALITY_THRESHOLD
        }), 400
    
    # Check Star King status
    star_result = check_star_king_status(github_user)
    
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            INSERT INTO bounty_submissions 
            (github_user, wallet_address, content_url, quality_score, is_star_king, bonus_multiplier, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            github_user, wallet_address, content_url,
            quality_result['overall_score'],
            star_result['is_star_king'],
            star_result['multiplier'],
            'approved'
        ))
    
    return jsonify({
        'status': 'approved',
        'quality_score': quality_result['overall_score'],
        'is_star_king': star_result['is_star_king'],
        'bonus_multiplier': star_result['multiplier'],
        'wallet_verified': True,
        'estimated_payout': calculate_payout(quality_result['overall_score'], star_result['multiplier'])
    })

def calculate_payout(quality_score, multiplier):
    base_payout = 100.0  # Base RustChain tokens
    quality_bonus = quality_score * 10
    return round((base_payout + quality_bonus) * multiplier, 2)

@app.route('/api/submissions')
def list_submissions():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT github_user, wallet_address, content_url, quality_score, 
                   is_star_king, bonus_multiplier, status, submitted_at
            FROM bounty_submissions 
            ORDER BY submitted_at DESC LIMIT 50
        ''')
        
        submissions = []
        for row in cursor.fetchall():
            submissions.append({
                'github_user': row[0],
                'wallet_address': row[1],
                'content_url': row[2],
                'quality_score': row[3],
                'is_star_king': bool(row[4]),
                'bonus_multiplier': row[5],
                'status': row[6],
                'submitted_at': row[7],
                'estimated_payout': calculate_payout(row[3] or 0, row[5] or 1.0)
            })
    
    return jsonify(submissions)

if __name__ == '__main__':
    init_database()
    app.run(debug=True, port=5001)