# SPDX-License-Identifier: MIT

import os
import sqlite3
import json
import time
import secrets
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template_string
from pathlib import Path

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Database configuration
DB_PATH = os.environ.get('HUMAN_FUNNEL_DB', 'human_funnel.db')

def get_db_path():
    return DB_PATH

def init_db():
    """Initialize the human funnel database"""
    schema_path = Path('human_funnel_schema.sql')
    if not schema_path.exists():
        # Create minimal schema if file doesn't exist
        with sqlite3.connect(DB_PATH) as conn:
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    wallet_address TEXT UNIQUE,
                    username TEXT UNIQUE,
                    email TEXT,
                    referral_code TEXT UNIQUE NOT NULL,
                    referred_by TEXT,
                    stage INTEGER DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_active DATETIME DEFAULT CURRENT_TIMESTAMP,
                    total_earnings_rtc REAL DEFAULT 0,
                    hardware_type TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    mining_setup_complete BOOLEAN DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS micro_bounties (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    bounty_type TEXT NOT NULL,
                    completed_at DATETIME,
                    reward_rtc REAL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS brag_cards (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    total_earned_rtc REAL DEFAULT 0,
                    mining_days INTEGER DEFAULT 0,
                    referrals_count INTEGER DEFAULT 0,
                    achievements_text TEXT,
                    generated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_users_referral_code ON users(referral_code);
                CREATE INDEX IF NOT EXISTS idx_users_wallet ON users(wallet_address);
                CREATE INDEX IF NOT EXISTS idx_bounties_user ON micro_bounties(user_id);
            ''')
    else:
        # Execute schema from file
        with sqlite3.connect(DB_PATH) as conn:
            with open(schema_path, 'r') as f:
                conn.executescript(f.read())

def validate_referral_code(code):
    """Validate referral code format"""
    if not code or len(code) < 6:
        return False
    return code.isalnum()

def generate_brag_card_data(user_id):
    """Generate brag card data for a user"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT u.username, u.total_earnings_rtc, u.created_at,
                   COUNT(DISTINCT mb.id) as bounties_completed,
                   COUNT(DISTINCT ref.id) as referrals_made
            FROM users u
            LEFT JOIN micro_bounties mb ON u.id = mb.user_id
            LEFT JOIN users ref ON u.referral_code = ref.referred_by
            WHERE u.id = ?
            GROUP BY u.id
        """, (user_id,))

        row = cursor.fetchone()
        if row:
            return {
                'username': row[0],
                'total_earned': row[1] or 0,
                'days_mining': (datetime.now() - datetime.fromisoformat(row[2].replace('Z', '+00:00'))).days,
                'bounties_completed': row[3] or 0,
                'referrals_made': row[4] or 0
            }
        return None

def calculate_hall_of_fame_rankings():
    """Calculate hall of fame rankings"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT u.username, u.total_earnings_rtc,
                   COUNT(DISTINCT ref.id) as referrals_count
            FROM users u
            LEFT JOIN users ref ON u.referral_code = ref.referred_by
            WHERE u.total_earnings_rtc > 0
            GROUP BY u.id
            ORDER BY u.total_earnings_rtc DESC, referrals_count DESC
            LIMIT 10
        """)

        return [{
            'username': row[0],
            'earnings': row[1],
            'referrals': row[2]
        } for row in cursor.fetchall()]

def process_micro_bounty_completion(user_id, bounty_type, reward_rtc):
    """Process micro bounty completion"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        # Check if already completed
        cursor.execute(
            "SELECT id FROM micro_bounties WHERE user_id = ? AND bounty_type = ?",
            (user_id, bounty_type)
        )
        if cursor.fetchone():
            return False

        # Add completion
        cursor.execute(
            "INSERT INTO micro_bounties (user_id, bounty_type, completed_at, reward_rtc) VALUES (?, ?, ?, ?)",
            (user_id, bounty_type, datetime.now().isoformat(), reward_rtc)
        )

        # Update user earnings
        cursor.execute(
            "UPDATE users SET total_earnings_rtc = total_earnings_rtc + ? WHERE id = ?",
            (reward_rtc, user_id)
        )

        conn.commit()
        return True

@app.route('/api/funnel/landing')
def landing_page():
    """Landing page endpoint"""
    hero_html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Rustchain - Mine RTC & Earn</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
    </head>
    <body>
        <div class="hero">
            <h1>Join the Rustchain Revolution</h1>
            <p>Mine RTC tokens with your hardware. Earn rewards. Build the future.</p>
            <div class="cta-buttons">
                <a href="/signup" class="btn-primary">Start Mining Now</a>
                <a href="/learn-more" class="btn-secondary">Learn More</a>
            </div>
        </div>
        <div class="features">
            <div class="feature">
                <h3>Easy Setup</h3>
                <p>Get started mining in minutes</p>
            </div>
            <div class="feature">
                <h3>Fair Rewards</h3>
                <p>Earn based on your contribution</p>
            </div>
            <div class="feature">
                <h3>Community Driven</h3>
                <p>Join thousands of miners worldwide</p>
            </div>
        </div>
    </body>
    </html>
    '''
    return render_template_string(hero_html)

@app.route('/api/funnel/hall-of-fame')
def hall_of_fame():
    """Hall of fame page"""
    rankings = calculate_hall_of_fame_rankings()

    hall_html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Rustchain Hall of Fame</title>
    </head>
    <body>
        <h1>Hall of Fame</h1>
        <div class="rankings">
            {% for rank, user in enumerate(rankings, 1) %}
            <div class="rank-{{ rank }}">
                <span class="position">#{{ rank }}</span>
                <span class="username">{{ user.username }}</span>
                <span class="earnings">{{ user.earnings }} RTC</span>
                <span class="referrals">{{ user.referrals }} referrals</span>
            </div>
            {% endfor %}
        </div>
    </body>
    </html>
    '''
    return render_template_string(hall_html, rankings=rankings, enumerate=enumerate)

@app.route('/api/funnel/brag-card/<int:user_id>')
def generate_brag_card(user_id):
    """Generate brag card for user"""
    data = generate_brag_card_data(user_id)
    if not data:
        return jsonify({'error': 'User not found'}), 404

    return jsonify({
        'success': True,
        'brag_card': data
    })

@app.route('/api/funnel/micro-bounty', methods=['POST'])
def complete_micro_bounty():
    """Complete a micro bounty"""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    user_id = data.get('user_id')
    bounty_type = data.get('bounty_type')
    reward_rtc = data.get('reward_rtc', 0.5)

    if not user_id or not bounty_type:
        return jsonify({'error': 'Missing required fields'}), 400

    success = process_micro_bounty_completion(user_id, bounty_type, reward_rtc)

    if success:
        return jsonify({'success': True, 'reward': reward_rtc})
    else:
        return jsonify({'error': 'Bounty already completed or invalid'}), 400

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
