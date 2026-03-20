// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import sqlite3
import json
import base64
import hashlib
from flask import Flask, request, jsonify, render_template_string
from datetime import datetime, timedelta
import os

DB_PATH = 'rustchain.db'

class BragCardGenerator:
    def __init__(self):
        self.init_db()

    def init_db(self):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS brag_cards (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    card_data TEXT NOT NULL,
                    card_hash TEXT UNIQUE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    template_id TEXT DEFAULT 'classic',
                    social_shares INTEGER DEFAULT 0
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS user_achievements (
                    username TEXT,
                    achievement_type TEXT,
                    achievement_value TEXT,
                    earned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (username, achievement_type)
                )
            ''')

    def validate_input(self, username, mining_stats, achievements, referral_count):
        errors = []

        if not username or len(username) < 3:
            errors.append("Username must be at least 3 characters")

        if not isinstance(mining_stats, dict):
            errors.append("Mining stats must be a valid object")

        required_mining_fields = ['blocks_mined', 'hash_rate', 'mining_days']
        for field in required_mining_fields:
            if field not in mining_stats:
                errors.append(f"Missing mining stat: {field}")

        if referral_count < 0:
            errors.append("Referral count cannot be negative")

        if not isinstance(achievements, list):
            errors.append("Achievements must be a list")

        return errors

    def get_user_stats(self, username):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # Get mining stats
            cursor.execute('''
                SELECT blocks_mined, total_hash_rate, days_mining
                FROM mining_stats WHERE username = ?
            ''', (username,))
            mining_data = cursor.fetchone()

            # Get achievements
            cursor.execute('''
                SELECT achievement_type, achievement_value
                FROM user_achievements WHERE username = ?
                ORDER BY earned_at DESC
            ''', (username,))
            achievements = cursor.fetchall()

            # Get referral count
            cursor.execute('''
                SELECT COUNT(*) FROM referrals WHERE referrer = ?
            ''', (username,))
            referral_count = cursor.fetchone()[0] if cursor.fetchone() else 0

            return {
                'mining_stats': {
                    'blocks_mined': mining_data[0] if mining_data else 0,
                    'hash_rate': mining_data[1] if mining_data else 0,
                    'mining_days': mining_data[2] if mining_data else 0
                },
                'achievements': achievements if achievements else [],
                'referral_count': referral_count
            }

    def generate_card_svg(self, username, template_id, mining_stats, achievements, referral_count):
        templates = {
            'classic': self._classic_template,
            'modern': self._modern_template,
            'minimal': self._minimal_template,
            'neon': self._neon_template
        }

        if template_id not in templates:
            template_id = 'classic'

        return templates[template_id](username, mining_stats, achievements, referral_count)

    def _classic_template(self, username, mining_stats, achievements, referral_count):
        achievement_badges = ""
        for i, (ach_type, ach_value) in enumerate(achievements[:3]):
            y_pos = 160 + (i * 30)
            achievement_badges += f'''
                <rect x="20" y="{y_pos}" width="160" height="25" fill="#2E7D32" rx="12"/>
                <text x="100" y="{y_pos + 17}" text-anchor="middle" fill="white" font-size="12" font-family="Arial">{ach_type}: {ach_value}</text>
            '''

        return f'''
        <svg width="400" height="300" xmlns="http://www.w3.org/2000/svg">
            <defs>
                <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" style="stop-color:#1976D2"/>
                    <stop offset="100%" style="stop-color:#0D47A1"/>
                </linearGradient>
            </defs>
            <rect width="400" height="300" fill="url(#bg)" rx="15"/>
            <rect x="10" y="10" width="380" height="280" fill="none" stroke="white" stroke-width="2" rx="10"/>

            <text x="200" y="40" text-anchor="middle" fill="white" font-size="24" font-family="Arial, sans-serif" font-weight="bold">RUSTCHAIN MINER</text>
            <text x="200" y="70" text-anchor="middle" fill="#FFD700" font-size="20" font-family="Arial, sans-serif">@{username}</text>

            <rect x="20" y="90" width="360" height="60" fill="rgba(255,255,255,0.1)" rx="8"/>
            <text x="30" y="110" fill="white" font-size="14" font-family="Arial, sans-serif">Blocks Mined: {mining_stats['blocks_mined']}</text>
            <text x="200" y="110" fill="white" font-size="14" font-family="Arial, sans-serif">Hash Rate: {mining_stats['hash_rate']} H/s</text>
            <text x="30" y="135" fill="white" font-size="14" font-family="Arial, sans-serif">Mining Days: {mining_stats['mining_days']}</text>
            <text x="200" y="135" fill="white" font-size="14" font-family="Arial, sans-serif">Referrals: {referral_count}</text>

            {achievement_badges}

            <text x="200" y="280" text-anchor="middle" fill="white" font-size="12" font-family="Arial, sans-serif">rustchain.network</text>
        </svg>
        '''

    def _modern_template(self, username, mining_stats, achievements, referral_count):
        return f'''
        <svg width="400" height="300" xmlns="http://www.w3.org/2000/svg">
            <rect width="400" height="300" fill="#0A0A0A" rx="20"/>
            <rect x="15" y="15" width="370" height="270" fill="#1A1A1A" rx="15"/>

            <circle cx="70" cy="70" r="30" fill="#FF6B35"/>
            <text x="70" y="77" text-anchor="middle" fill="white" font-size="20" font-family="Arial, sans-serif" font-weight="bold">{username[0].upper()}</text>

            <text x="120" y="60" fill="white" font-size="18" font-family="Arial, sans-serif" font-weight="bold">{username}</text>
            <text x="120" y="80" fill="#888" font-size="14" font-family="Arial, sans-serif">Rustchain Miner</text>

            <rect x="30" y="120" width="340" height="1" fill="#333"/>

            <text x="30" y="150" fill="#FF6B35" font-size="12" font-family="Arial, sans-serif">MINING POWER</text>
            <text x="30" y="170" fill="white" font-size="16" font-family="Arial, sans-serif">{mining_stats['blocks_mined']} blocks • {mining_stats['hash_rate']} H/s</text>

            <text x="30" y="200" fill="#FF6B35" font-size="12" font-family="Arial, sans-serif">NETWORK GROWTH</text>
            <text x="30" y="220" fill="white" font-size="16" font-family="Arial, sans-serif">{referral_count} referrals • {mining_stats['mining_days']} days active</text>

            <text x="370" y="280" text-anchor="end" fill="#555" font-size="10" font-family="Arial, sans-serif">rustchain.network</text>
        </svg>
        '''

    def _minimal_template(self, username, mining_stats, achievements, referral_count):
        return f'''
        <svg width="400" height="300" xmlns="http://www.w3.org/2000/svg">
            <rect width="400" height="300" fill="white" rx="10"/>
            <rect x="5" y="5" width="390" height="290" fill="none" stroke="#E0E0E0" stroke-width="1" rx="8"/>

            <text x="200" y="50" text-anchor="middle" fill="#212121" font-size="20" font-family="Arial, sans-serif" font-weight="300">@{username}</text>
            <rect x="150" y="60" width="100" height="1" fill="#2196F3"/>

            <text x="80" y="120" text-anchor="middle" fill="#666" font-size="12" font-family="Arial, sans-serif">BLOCKS</text>
            <text x="80" y="140" text-anchor="middle" fill="#212121" font-size="24" font-family="Arial, sans-serif" font-weight="bold">{mining_stats['blocks_mined']}</text>

            <text x="200" y="120" text-anchor="middle" fill="#666" font-size="12" font-family="Arial, sans-serif">HASH RATE</text>
            <text x="200" y="140" text-anchor="middle" fill="#212121" font-size="24" font-family="Arial, sans-serif" font-weight="bold">{mining_stats['hash_rate']}</text>

            <text x="320" y="120" text-anchor="middle" fill="#666" font-size="12" font-family="Arial, sans-serif">REFERRALS</text>
            <text x="320" y="140" text-anchor="middle" fill="#212121" font-size="24" font-family="Arial, sans-serif" font-weight="bold">{referral_count}</text>

            <text x="200" y="200" text-anchor="middle" fill="#999" font-size="14" font-family="Arial, sans-serif">{mining_stats['mining_days']} days mining</text>

            <text x="200" y="280" text-anchor="middle" fill="#BBB" font-size="10" font-family="Arial, sans-serif">rustchain.network</text>
        </svg>
        '''

    def _neon_template(self, username, mining_stats, achievements, referral_count):
        return f'''
        <svg width="400" height="300" xmlns="http://www.w3.org/2000/svg">
            <defs>
                <filter id="glow">
                    <feGaussianBlur stdDeviation="3" result="coloredBlur"/>
                    <feMerge>
                        <feMergeNode in="coloredBlur"/>
                        <feMergeNode in="SourceGraphic"/>
                    </feMerge>
                </filter>
            </defs>
            <rect width="400" height="300" fill="#0D0015" rx="15"/>

            <text x="200" y="50" text-anchor="middle" fill="#00FFFF" font-size="20" font-family="Arial, sans-serif" font-weight="bold" filter="url(#glow)">{username}</text>
            <text x="200" y="75" text-anchor="middle" fill="#FF00FF" font-size="14" font-family="Arial, sans-serif" filter="url(#glow)">RUSTCHAIN ELITE</text>

            <rect x="20" y="100" width="360" height="80" fill="none" stroke="#00FFFF" stroke-width="2" rx="10" filter="url(#glow)"/>

            <text x="40" y="125" fill="#00FFFF" font-size="12" font-family="Arial, sans-serif">BLOCKS: {mining_stats['blocks_mined']}</text>
            <text x="200" y="125" fill="#FF00FF" font-size="12" font-family="Arial, sans-serif">HASH: {mining_stats['hash_rate']} H/s</text>
            <text x="40" y="150" fill="#00FF00" font-size="12" font-family="Arial, sans-serif">DAYS: {mining_stats['mining_days']}</text>
            <text x="200" y="150" fill="#FFFF00" font-size="12" font-family="Arial, sans-serif">REFS: {referral_count}</text>

            <text x="200" y="220" text-anchor="middle" fill="#888" font-size="11" font-family="Arial, sans-serif">PROOF OF WORK • PROOF OF HUMANITY</text>

            <text x="200" y="280" text-anchor="middle" fill="#00FFFF" font-size="10" font-family="Arial, sans-serif" filter="url(#glow)">rustchain.network</text>
        </svg>
        '''

    def save_brag_card(self, username, card_data, template_id):
        card_json = json.dumps(card_data)
        card_hash = hashlib.sha256(f"{username}{card_json}{template_id}".encode()).hexdigest()

        with sqlite3.connect(DB_PATH) as conn:
            try:
                conn.execute('''
                    INSERT INTO brag_cards (username, card_data, card_hash, template_id)
                    VALUES (?, ?, ?, ?)
                ''', (username, card_json, card_hash, template_id))
                return card_hash
            except sqlite3.IntegrityError:
                return card_hash

    def get_social_optimized_meta(self, card_hash):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT username, card_data FROM brag_cards WHERE card_hash = ?
            ''', (card_hash,))
            result = cursor.fetchone()

        if not result:
            return None

        username, card_data_str = result
        card_data = json.loads(card_data_str)
        mining_stats = card_data['mining_stats']

        return {
            'title': f"{username}'s Rustchain Mining Achievement",
            'description': f"Mining for {mining_stats['mining_days']} days • {mining_stats['blocks_mined']} blocks mined • {card_data['referral_count']} referrals",
            'image_url': f"/brag-card/{card_hash}.svg",
            'twitter_card': 'summary_large_image',
            'og_type': 'website'
        }

app = Flask(__name__)
brag_gen = BragCardGenerator()

@app.route('/api/brag-card/generate', methods=['POST'])
def generate_brag_card():
    data = request.json
    username = data.get('username', '').strip()
    template_id = data.get('template', 'classic')

    user_stats = brag_gen.get_user_stats(username)
    if not user_stats:
        return jsonify({'error': 'User not found'}), 404

    errors = brag_gen.validate_input(
        username,
        user_stats['mining_stats'],
        user_stats['achievements'],
        user_stats['referral_count']
    )

    if errors:
        return jsonify({'errors': errors}), 400

    svg_content = brag_gen.generate_card_svg(
        username,
        template_id,
        user_stats['mining_stats'],
        user_stats['achievements'],
        user_stats['referral_count']
    )

    card_hash = brag_gen.save_brag_card(username, user_stats, template_id)

    return jsonify({
        'success': True,
        'card_hash': card_hash,
        'svg_content': svg_content,
        'share_url': f"/brag-card/{card_hash}",
        'download_url': f"/brag-card/{card_hash}.svg"
    })

@app.route('/brag-card/<card_hash>')
def view_brag_card(card_hash):
    meta = brag_gen.get_social_optimized_meta(card_hash)
    if not meta:
        return "Card not found", 404

    html_template = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>{{ meta.title }}</title>
        <meta name="description" content="{{ meta.description }}">
        <meta property="og:title" content="{{ meta.title }}">
        <meta property="og:description" content="{{ meta.description }}">
        <meta property="og:image" content="{{ request.url_root[:-1] + meta.image_url }}">
        <meta property="og:type" content="{{ meta.og_type }}">
        <meta name="twitter:card" content="{{ meta.twitter_card }}">
        <meta name="twitter:title" content="{{ meta.title }}">
        <meta name="twitter:description" content="{{ meta.description }}">
        <meta name="twitter:image" content="{{ request.url_root[:-1] + meta.image_url }}">
        <style>
            body { margin: 0; padding: 20px; background: #f5f5f5; font-family: Arial, sans-serif; }
            .card-container { max-width: 400px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
            .share-buttons { margin-top: 20px; text-align: center; }
            .share-btn { display: inline-block; margin: 0 10px; padding: 10px 20px; background: #1976D2; color: white; text-decoration: none; border-radius: 5px; }
        </style>
    </head>
    <body>
        <div class="card-container">
            <img src="{{ meta.image_url }}" alt="Brag Card" style="width: 100%; height: auto;">
            <div class="share-buttons">
                <a href="https://twitter.com/intent/tweet?url={{ request.url }}&text=Check out my Rustchain mining achievements!" class="share-btn">Share on Twitter</a>
                <a href="{{ meta.image_url }}" download class="share-btn">Download SVG</a>
            </div>
        </div>
    </body>
    </html>
    '''

    return render_template_string(html_template, meta=meta)

@app.route('/brag-card/<card_hash>.svg')
def serve_card_svg(card_hash):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT username, card_data, template_id FROM brag_cards WHERE card_hash = ?
        ''', (card_hash,))
        result = cursor.fetchone()

    if not result:
        return "Not found", 404

    username, card_data_str, template_id = result
    card_data = json.loads(card_data_str)

    svg_content = brag_gen.generate_card_svg(
        username,
        template_id,
        card_data['mining_stats'],
        card_data['achievements'],
        card_data['referral_count']
    )

    response = app.response_class(
        svg_content,
        mimetype='image/svg+xml',
        headers={'Cache-Control': 'public, max-age=3600'}
    )
    return response

if __name__ == '__main__':
    app.run(debug=True)
