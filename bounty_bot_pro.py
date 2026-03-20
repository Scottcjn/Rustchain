// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import sqlite3
import time
import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse
import requests
from flask import Flask, render_template_string, request, jsonify, redirect, url_for
import google.generativeai as genai
from bs4 import BeautifulSoup
import re

DB_PATH = "bounty_bot_pro.db"
GEMINI_API_KEY = "your_gemini_api_key_here"
NODE_API_BASE = "http://localhost:3030"
MIN_STAR_KING_BALANCE = 1000.0
STAR_KING_BONUS_MULTIPLIER = 2.5

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

def init_database():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bounty_submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wallet_address TEXT NOT NULL,
                github_username TEXT NOT NULL,
                submission_type TEXT NOT NULL,
                content_url TEXT NOT NULL,
                content_hash TEXT UNIQUE NOT NULL,
                ai_quality_score REAL DEFAULT 0.0,
                technical_depth REAL DEFAULT 0.0,
                clarity REAL DEFAULT 0.0,
                originality REAL DEFAULT 0.0,
                is_star_king BOOLEAN DEFAULT FALSE,
                wallet_balance REAL DEFAULT 0.0,
                bonus_multiplier REAL DEFAULT 1.0,
                calculated_reward REAL DEFAULT 0.0,
                status TEXT DEFAULT 'pending',
                created_at TEXT NOT NULL,
                processed_at TEXT,
                feedback TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS quality_reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                submission_id INTEGER NOT NULL,
                reviewer_type TEXT NOT NULL,
                review_data TEXT NOT NULL,
                score REAL NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (submission_id) REFERENCES bounty_submissions (id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS node_verifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wallet_address TEXT NOT NULL,
                balance REAL DEFAULT 0.0,
                last_verified TEXT NOT NULL,
                status TEXT NOT NULL
            )
        ''')
        conn.commit()

class GeminiContentAnalyzer:
    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-pro')

    def analyze_content(self, content: str, url: str = "") -> Dict[str, float]:
        prompt = f"""
        Analyze the following content for technical quality in the context of blockchain/RustChain development:

        URL: {url}
        Content: {content[:3000]}...

        Rate on a scale of 0-10 for:
        1. Technical Depth - How technically sophisticated and detailed is the content?
        2. Clarity - How well-written and clear is the explanation?
        3. Originality - How unique and valuable is the contribution?

        Respond ONLY in JSON format:
        {{
            "technical_depth": X.X,
            "clarity": X.X,
            "originality": X.X,
            "reasoning": "Brief explanation"
        }}
        """

        try:
            response = self.model.generate_content(prompt)
            result = json.loads(response.text.strip())

            tech_score = max(0.0, min(10.0, float(result.get('technical_depth', 0))))
            clarity_score = max(0.0, min(10.0, float(result.get('clarity', 0))))
            orig_score = max(0.0, min(10.0, float(result.get('originality', 0))))

            overall = (tech_score + clarity_score + orig_score) / 3.0

            return {
                'technical_depth': tech_score,
                'clarity': clarity_score,
                'originality': orig_score,
                'overall_score': overall,
                'reasoning': result.get('reasoning', '')
            }
        except Exception as e:
            logger.error(f"Gemini analysis failed: {e}")
            return {
                'technical_depth': 5.0,
                'clarity': 5.0,
                'originality': 5.0,
                'overall_score': 5.0,
                'reasoning': f'Analysis failed: {str(e)}'
            }

class NodeIntegration:
    def __init__(self, base_url: str):
        self.base_url = base_url

    def verify_wallet(self, wallet_address: str) -> Tuple[bool, float]:
        try:
            response = requests.get(
                f"{self.base_url}/wallet/balance",
                params={'address': wallet_address},
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                balance = float(data.get('balance', 0.0))
                return True, balance
            else:
                logger.warning(f"Wallet verification failed: {response.status_code}")
                return False, 0.0

        except Exception as e:
            logger.error(f"Node connection failed: {e}")
            return False, 0.0

    def is_star_king(self, balance: float) -> bool:
        return balance >= MIN_STAR_KING_BALANCE

class ContentExtractor:
    @staticmethod
    def extract_from_url(url: str) -> str:
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            for script in soup(["script", "style"]):
                script.decompose()

            text = soup.get_text()
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)

            return text[:5000]

        except Exception as e:
            logger.error(f"Content extraction failed for {url}: {e}")
            return ""

class BountyBotPro:
    def __init__(self):
        self.analyzer = GeminiContentAnalyzer(GEMINI_API_KEY)
        self.node = NodeIntegration(NODE_API_BASE)
        self.extractor = ContentExtractor()

    def calculate_reward(self, quality_score: float, is_star_king: bool) -> float:
        base_reward = quality_score * 10.0

        if is_star_king:
            return base_reward * STAR_KING_BONUS_MULTIPLIER
        return base_reward

    def process_submission(self, wallet_address: str, github_username: str,
                         submission_type: str, content_url: str) -> Dict:

        content_hash = hashlib.sha256(f"{wallet_address}:{content_url}".encode()).hexdigest()

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT id FROM bounty_submissions WHERE content_hash = ?',
                (content_hash,)
            )
            if cursor.fetchone():
                return {'error': 'Submission already exists', 'duplicate': True}

        wallet_valid, wallet_balance = self.node.verify_wallet(wallet_address)
        if not wallet_valid:
            return {'error': 'Invalid or unreachable wallet address', 'wallet_error': True}

        content = self.extractor.extract_from_url(content_url)
        if not content or len(content.strip()) < 100:
            return {'error': 'Insufficient content extracted from URL', 'content_error': True}

        analysis = self.analyzer.analyze_content(content, content_url)
        is_star_king = self.node.is_star_king(wallet_balance)
        bonus_mult = STAR_KING_BONUS_MULTIPLIER if is_star_king else 1.0
        reward = self.calculate_reward(analysis['overall_score'], is_star_king)

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO bounty_submissions (
                    wallet_address, github_username, submission_type, content_url,
                    content_hash, ai_quality_score, technical_depth, clarity,
                    originality, is_star_king, wallet_balance, bonus_multiplier,
                    calculated_reward, status, created_at, feedback
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                wallet_address, github_username, submission_type, content_url,
                content_hash, analysis['overall_score'], analysis['technical_depth'],
                analysis['clarity'], analysis['originality'], is_star_king,
                wallet_balance, bonus_mult, reward, 'processed',
                datetime.utcnow().isoformat(), analysis['reasoning']
            ))

            submission_id = cursor.lastrowid

            cursor.execute('''
                INSERT INTO quality_reviews (submission_id, reviewer_type, review_data, score, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                submission_id, 'gemini_1.5_pro', json.dumps(analysis),
                analysis['overall_score'], datetime.utcnow().isoformat()
            ))

            cursor.execute('''
                INSERT INTO node_verifications (wallet_address, balance, last_verified, status)
                VALUES (?, ?, ?, ?)
            ''', (wallet_address, wallet_balance, datetime.utcnow().isoformat(), 'verified'))

            conn.commit()

        return {
            'success': True,
            'submission_id': submission_id,
            'quality_score': analysis['overall_score'],
            'is_star_king': is_star_king,
            'calculated_reward': reward,
            'technical_scores': {
                'depth': analysis['technical_depth'],
                'clarity': analysis['clarity'],
                'originality': analysis['originality']
            },
            'wallet_balance': wallet_balance,
            'reasoning': analysis['reasoning']
        }

bot = BountyBotPro()

@app.route('/')
def dashboard():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT COUNT(*), AVG(ai_quality_score), SUM(calculated_reward)
            FROM bounty_submissions WHERE status = 'processed'
        ''')
        stats = cursor.fetchone()

        cursor.execute('''
            SELECT id, github_username, submission_type, ai_quality_score,
                   is_star_king, calculated_reward, created_at
            FROM bounty_submissions
            ORDER BY created_at DESC LIMIT 10
        ''')
        recent = cursor.fetchall()

    html = '''
    <!DOCTYPE html>
    <html>
    <head><title>Bounty Bot PRO Dashboard</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 40px; background: #f5f7fa; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px; margin-bottom: 30px; }
        .stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-bottom: 30px; }
        .stat-card { background: white; padding: 25px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); text-align: center; }
        .stat-number { font-size: 32px; font-weight: bold; color: #667eea; }
        .form-section { background: white; padding: 30px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 30px; }
        .form-group { margin-bottom: 20px; }
        .form-group label { display: block; font-weight: bold; margin-bottom: 8px; color: #333; }
        .form-group input, .form-group select { width: 100%; padding: 12px; border: 2px solid #e1e8ed; border-radius: 6px; font-size: 16px; }
        .submit-btn { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 14px 28px; border: none; border-radius: 6px; font-size: 16px; cursor: pointer; font-weight: bold; }
        .submit-btn:hover { opacity: 0.9; }
        .recent-table { background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        .recent-table table { width: 100%; border-collapse: collapse; }
        .recent-table th { background: #667eea; color: white; padding: 15px; text-align: left; }
        .recent-table td { padding: 12px 15px; border-bottom: 1px solid #e1e8ed; }
        .star-king { color: #f39c12; font-weight: bold; }
        .quality-score { font-weight: bold; }
        .quality-high { color: #27ae60; }
        .quality-med { color: #f39c12; }
        .quality-low { color: #e74c3c; }
    </style>
    </head>
    <body>
        <div class="header">
            <h1>🚀 Bounty Bot PRO Dashboard</h1>
            <p>AI-Powered Quality Scoring • RustChain Node Integration • Star King Detection</p>
        </div>

        <div class="stats">
            <div class="stat-card">
                <div class="stat-number">{{ stats[0] or 0 }}</div>
                <div>Total Submissions</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{{ "%.1f"|format(stats[1] or 0) }}</div>
                <div>Avg Quality Score</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{{ "%.2f"|format(stats[2] or 0) }}</div>
                <div>Total Rewards</div>
            </div>
        </div>

        <div class="form-section">
            <h2>Submit Content for Review</h2>
            <form action="/submit" method="post">
                <div class="form-group">
                    <label>Wallet Address:</label>
                    <input type="text" name="wallet_address" required placeholder="rust1..." />
                </div>
                <div class="form-group">
                    <label>GitHub Username:</label>
                    <input type="text" name="github_username" required placeholder="your-github-handle" />
                </div>
                <div class="form-group">
                    <label>Submission Type:</label>
                    <select name="submission_type" required>
                        <option value="">Select Type</option>
                        <option value="article">Technical Article</option>
                        <option value="tutorial">Tutorial/Guide</option>
                        <option value="documentation">Documentation</option>
                        <option value="analysis">Market Analysis</option>
                        <option value="other">Other</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Content URL:</label>
                    <input type="url" name="content_url" required placeholder="https://..." />
                </div>
                <button type="submit" class="submit-btn">Submit for AI Analysis</button>
            </form>
        </div>

        <div class="recent-table">
            <h2 style="margin: 0; padding: 20px; background: #f8f9fa;">Recent Submissions</h2>
            <table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>User</th>
                        <th>Type</th>
                        <th>Quality Score</th>
                        <th>Star King</th>
                        <th>Reward</th>
                        <th>Date</th>
                    </tr>
                </thead>
                <tbody>
                {% for row in recent %}
                    <tr>
                        <td>#{{ row[0] }}</td>
                        <td>{{ row[1] }}</td>
                        <td>{{ row[2] }}</td>
                        <td>
                            <span class="quality-score {% if row[3] >= 7 %}quality-high{% elif row[3] >= 5 %}quality-med{% else %}quality-low{% endif %}">
                                {{ "%.1f"|format(row[3]) }}/10
                            </span>
                        </td>
                        <td>
                            {% if row[4] %}
                                <span class="star-king">⭐ Star King</span>
                            {% else %}
                                Regular
                            {% endif %}
                        </td>
                        <td>{{ "%.2f"|format(row[5]) }}</td>
                        <td>{{ row[6][:10] }}</td>
                    </tr>
                {% endfor %}
                </tbody>
            </table>
        </div>
    </body>
    </html>
    '''
    return render_template_string(html, stats=stats, recent=recent)

@app.route('/submit', methods=['POST'])
def submit_content():
    wallet_address = request.form.get('wallet_address', '').strip()
    github_username = request.form.get('github_username', '').strip()
    submission_type = request.form.get('submission_type', '').strip()
    content_url = request.form.get('content_url', '').strip()

    if not all([wallet_address, github_username, submission_type, content_url]):
        return jsonify({'error': 'All fields required'}), 400

    result = bot.process_submission(wallet_address, github_username, submission_type, content_url)

    if 'error' in result:
        return jsonify(result), 400

    return jsonify(result)

@app.route('/api/submission/<int:submission_id>')
def get_submission(submission_id):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM bounty_submissions WHERE id = ?
        ''', (submission_id,))
        row = cursor.fetchone()

        if not row:
            return jsonify({'error': 'Submission not found'}), 404

        columns = [desc[0] for desc in cursor.description]
        submission = dict(zip(columns, row))

        cursor.execute('''
            SELECT reviewer_type, review_data, score, created_at
            FROM quality_reviews WHERE submission_id = ?
        ''', (submission_id,))
        reviews = cursor.fetchall()

        submission['reviews'] = [
            {
                'reviewer': r[0],
                'data': json.loads(r[1]) if r[1] else {},
                'score': r[2],
                'created_at': r[3]
            } for r in reviews
        ]

    return jsonify(submission)

@app.route('/api/stats')
def api_stats():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        cursor.execute('''
            SELECT
                COUNT(*) as total_submissions,
                AVG(ai_quality_score) as avg_quality,
                SUM(calculated_reward) as total_rewards,
                COUNT(CASE WHEN is_star_king THEN 1 END) as star_kings
            FROM bounty_submissions WHERE status = 'processed'
        ''')
        stats = cursor.fetchone()

        cursor.execute('''
            SELECT submission_type, COUNT(*), AVG(ai_quality_score)
            FROM bounty_submissions
            WHERE status = 'processed'
            GROUP BY submission_type
        ''')
        by_type = cursor.fetchall()

    return jsonify({
        'total_submissions': stats[0] or 0,
        'avg_quality': round(stats[1] or 0, 2),
        'total_rewards': round(stats[2] or 0, 2),
        'star_kings': stats[3] or 0,
        'by_type': [{'type': t[0], 'count': t[1], 'avg_quality': round(t[2], 2)} for t in by_type]
    })

if __name__ == '__main__':
    init_database()
    app.run(debug=True, port=5001)
