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
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
            ''')
    else:
        with open(schema_path, 'r') as f:
            schema = f.read()
        with sqlite3.connect(DB_PATH) as conn:
            conn.executescript(schema)

def validate_referral_code(referral_code):
    """Validate if referral code exists and is active"""
    if not referral_code:
        return False

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM users WHERE referral_code = ? AND is_active = 1",
            (referral_code,)
        )
        return cursor.fetchone() is not None

def generate_brag_card_data(user_id):
    """Generate brag card data for a user"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        # Get user data
        cursor.execute(
            "SELECT username, total_earnings_rtc FROM users WHERE id = ?",
            (user_id,)
        )
        user_data = cursor.fetchone()

        if not user_data:
            return None

        # Get referrals count
        cursor.execute(
            "SELECT COUNT(*) FROM users WHERE referred_by IN (SELECT referral_code FROM users WHERE id = ?)",
            (user_id,)
        )
        referrals_count = cursor.fetchone()[0]

        # Get completed bounties
        cursor.execute(
            "SELECT COUNT(*), SUM(reward_rtc) FROM micro_bounties WHERE user_id = ? AND completed_at IS NOT NULL",
            (user_id,)
        )
        bounty_data = cursor.fetchone()

        return {
            'username': user_data[0],
            'total_earnings': user_data[1],
            'referrals_count': referrals_count,
            'bounties_completed': bounty_data[0] or 0,
            'bounty_earnings': bounty_data[1] or 0
        }

def calculate_hall_of_fame_rankings():
    """Calculate and return hall of fame rankings"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT username, total_earnings_rtc,
                   (SELECT COUNT(*) FROM users u2 WHERE u2.referred_by = u1.referral_code) as referrals
            FROM users u1
            WHERE is_active = 1
            ORDER BY total_earnings_rtc DESC
            LIMIT 10
        """)
        return cursor.fetchall()

def process_micro_bounty_completion(user_id, bounty_type, reward_rtc):
    """Process completion of a micro bounty"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        # Record bounty completion
        cursor.execute("""
            INSERT INTO micro_bounties (user_id, bounty_type, completed_at, reward_rtc)
            VALUES (?, ?, CURRENT_TIMESTAMP, ?)
        """, (user_id, bounty_type, reward_rtc))

        # Update user earnings
        cursor.execute("""
            UPDATE users
            SET total_earnings_rtc = total_earnings_rtc + ?
            WHERE id = ?
        """, (reward_rtc, user_id))

        conn.commit()
        return True

@app.route('/api/funnel/landing', methods=['GET'])
def landing_page():
    """Stage 1: Landing page with referral tracking"""
    referral_code = request.args.get('ref', '')

    html_template = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Rustchain - Next-Gen Mining Platform</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { font-family: Arial, sans-serif; margin: 0; background: #1a1a1a; color: #fff; }
            .container { max-width: 800px; margin: 0 auto; padding: 20px; }
            .hero { text-align: center; padding: 60px 20px; }
            .cta-button { background: #ff6600; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; font-size: 18px; }
            .referral-bonus { background: #2d5a2d; padding: 15px; border-radius: 8px; margin: 20px 0; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="hero">
                <h1>Welcome to Rustchain</h1>
                <p>Join the next generation of decentralized mining</p>
                {% if referral_code %}
                <div class="referral-bonus">
                    <h3>🎉 Special Referral Bonus!</h3>
                    <p>You've been invited by a Rustchain miner. Get bonus RTC when you start mining!</p>
                </div>
                {% endif %}
                <a href="/api/funnel/signup?ref={{ referral_code }}" class="cta-button">Start Mining Now</a>
            </div>
        </div>
    </body>
    </html>
    '''

    return render_template_string(html_template, referral_code=referral_code)

@app.route('/api/funnel/brag-card/<user_id>', methods=['GET'])
def generate_brag_card(user_id):
    """Generate shareable brag card for user achievements"""
    try:
        user_id = int(user_id)
        card_data = generate_brag_card_data(user_id)

        if not card_data:
            return jsonify({'error': 'User not found'}), 404

        html_template = '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>{{ username }}'s Rustchain Stats</title>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body { font-family: Arial, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); margin: 0; padding: 20px; }
                .brag-card { max-width: 400px; margin: 0 auto; background: white; border-radius: 15px; padding: 30px; text-align: center; box-shadow: 0 10px 30px rgba(0,0,0,0.3); }
                .username { font-size: 24px; font-weight: bold; color: #333; margin-bottom: 20px; }
                .stat { margin: 15px 0; }
                .stat-value { font-size: 28px; font-weight: bold; color: #ff6600; }
                .stat-label { font-size: 14px; color: #666; text-transform: uppercase; }
                .join-btn { background: #ff6600; color: white; padding: 12px 25px; text-decoration: none; border-radius: 25px; margin-top: 20px; display: inline-block; }
            </style>
        </head>
        <body>
            <div class="brag-card">
                <div class="username">{{ username }}</div>
                <div class="stat">
                    <div class="stat-value">{{ "%.2f"|format(total_earnings) }}</div>
                    <div class="stat-label">RTC Earned</div>
                </div>
                <div class="stat">
                    <div class="stat-value">{{ referrals_count }}</div>
                    <div class="stat-label">Referrals</div>
                </div>
                <div class="stat">
                    <div class="stat-value">{{ bounties_completed }}</div>
                    <div class="stat-label">Bounties Completed</div>
                </div>
                <a href="/api/funnel/landing" class="join-btn">Join Rustchain</a>
            </div>
        </body>
        </html>
        '''

        return render_template_string(html_template, **card_data)

    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid user ID'}), 400

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
