// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import sqlite3
import secrets
import hashlib
import time
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template_string
import json

DB_PATH = 'rustchain.db'

class ReferralSystem:
    def __init__(self):
        self.init_db()

    def init_db(self):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # Referral codes table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS referral_codes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT UNIQUE NOT NULL,
                    user_id TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1
                )
            ''')

            # Referral tracking table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS referrals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    referrer_code TEXT NOT NULL,
                    referred_user_id TEXT NOT NULL,
                    conversion_type TEXT DEFAULT 'signup',
                    rtc_earned REAL DEFAULT 0.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_verified BOOLEAN DEFAULT 0
                )
            ''')

            # Weekly leaderboard
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS weekly_leaderboard (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    week_start DATE NOT NULL,
                    user_id TEXT NOT NULL,
                    referral_count INTEGER DEFAULT 0,
                    total_rtc_earned REAL DEFAULT 0.0,
                    bonus_rtc REAL DEFAULT 0.0,
                    rank_position INTEGER,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Prize distribution log
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS prize_distribution (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    week_start DATE NOT NULL,
                    user_id TEXT NOT NULL,
                    rank_position INTEGER,
                    prize_rtc REAL NOT NULL,
                    distributed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    tx_hash TEXT
                )
            ''')

            conn.commit()

    def generate_referral_code(self, user_id):
        """Generate unique referral code for user"""
        base_code = secrets.token_urlsafe(6).upper()
        user_hash = hashlib.md5(user_id.encode()).hexdigest()[:4].upper()
        code = f"RTC{base_code}{user_hash}"

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('''
                    INSERT INTO referral_codes (code, user_id)
                    VALUES (?, ?)
                ''', (code, user_id))
                conn.commit()
                return code
            except sqlite3.IntegrityError:
                return self.generate_referral_code(user_id)

    def get_user_referral_code(self, user_id):
        """Get existing referral code or create new one"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT code FROM referral_codes
                WHERE user_id = ? AND is_active = 1
                ORDER BY created_at DESC LIMIT 1
            ''', (user_id,))

            result = cursor.fetchone()
            if result:
                return result[0]
            else:
                return self.generate_referral_code(user_id)

    def process_referral(self, referral_code, new_user_id, conversion_type='signup'):
        """Track referral conversion and award RTC"""
        rtc_rewards = {
            'signup': 5.0,
            'first_mine': 10.0,
            'retention_7d': 15.0
        }

        rtc_earned = rtc_rewards.get(conversion_type, 5.0)

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # Verify referral code exists
            cursor.execute('''
                SELECT user_id FROM referral_codes
                WHERE code = ? AND is_active = 1
            ''', (referral_code,))

            referrer = cursor.fetchone()
            if not referrer:
                return False, "Invalid referral code"

            # Check for duplicate referral
            cursor.execute('''
                SELECT id FROM referrals
                WHERE referrer_code = ? AND referred_user_id = ?
            ''', (referral_code, new_user_id))

            if cursor.fetchone():
                return False, "Referral already processed"

            # Record referral
            cursor.execute('''
                INSERT INTO referrals (referrer_code, referred_user_id, conversion_type, rtc_earned)
                VALUES (?, ?, ?, ?)
            ''', (referral_code, new_user_id, conversion_type, rtc_earned))

            # Update weekly leaderboard
            self.update_weekly_stats(referrer[0], rtc_earned)

            conn.commit()
            return True, f"Referral processed! {rtc_earned} RTC earned"

    def update_weekly_stats(self, user_id, rtc_earned):
        """Update weekly leaderboard stats"""
        week_start = self.get_current_week_start()

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            cursor.execute('''
                INSERT OR IGNORE INTO weekly_leaderboard
                (week_start, user_id, referral_count, total_rtc_earned)
                VALUES (?, ?, 0, 0.0)
            ''', (week_start, user_id))

            cursor.execute('''
                UPDATE weekly_leaderboard
                SET referral_count = referral_count + 1,
                    total_rtc_earned = total_rtc_earned + ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE week_start = ? AND user_id = ?
            ''', (rtc_earned, week_start, user_id))

            conn.commit()

    def get_current_week_start(self):
        """Get start date of current week (Monday)"""
        today = datetime.now().date()
        days_since_monday = today.weekday()
        week_start = today - timedelta(days=days_since_monday)
        return week_start

    def get_weekly_leaderboard(self, week_start=None):
        """Get current weekly leaderboard with rankings"""
        if not week_start:
            week_start = self.get_current_week_start()

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT user_id, referral_count, total_rtc_earned, bonus_rtc,
                       ROW_NUMBER() OVER (ORDER BY referral_count DESC, total_rtc_earned DESC) as rank
                FROM weekly_leaderboard
                WHERE week_start = ?
                ORDER BY referral_count DESC, total_rtc_earned DESC
                LIMIT 20
            ''', (week_start,))

            return cursor.fetchall()

    def distribute_weekly_prizes(self):
        """Distribute prizes for completed week"""
        last_week_start = self.get_current_week_start() - timedelta(days=7)
        leaderboard = self.get_weekly_leaderboard(last_week_start)

        # Prize structure: Top 10 get bonus RTC
        prize_tiers = {
            1: 100.0,  # 1st place
            2: 75.0,   # 2nd place
            3: 50.0,   # 3rd place
            4: 30.0,   # 4th-5th place
            5: 30.0,
            6: 20.0,   # 6th-10th place
            7: 20.0,
            8: 20.0,
            9: 20.0,
            10: 20.0
        }

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            for entry in leaderboard[:10]:
                user_id, ref_count, total_rtc, bonus_rtc, rank = entry
                prize_amount = prize_tiers.get(rank, 0.0)

                if prize_amount > 0:
                    cursor.execute('''
                        INSERT INTO prize_distribution
                        (week_start, user_id, rank_position, prize_rtc)
                        VALUES (?, ?, ?, ?)
                    ''', (last_week_start, user_id, rank, prize_amount))

                    # Update leaderboard with bonus
                    cursor.execute('''
                        UPDATE weekly_leaderboard
                        SET bonus_rtc = ?, rank_position = ?
                        WHERE week_start = ? AND user_id = ?
                    ''', (prize_amount, rank, last_week_start, user_id))

            conn.commit()
            return len([p for p in prize_tiers.values() if p > 0])

    def get_user_stats(self, user_id):
        """Get comprehensive referral stats for user"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # Total referrals and earnings
            cursor.execute('''
                SELECT COUNT(*) as total_referrals,
                       COALESCE(SUM(rtc_earned), 0) as total_rtc
                FROM referrals r
                JOIN referral_codes rc ON r.referrer_code = rc.code
                WHERE rc.user_id = ?
            ''', (user_id,))

            total_stats = cursor.fetchone()

            # Current week stats
            week_start = self.get_current_week_start()
            cursor.execute('''
                SELECT referral_count, total_rtc_earned, bonus_rtc,
                       (SELECT COUNT(*) + 1 FROM weekly_leaderboard w2
                        WHERE w2.week_start = w1.week_start
                        AND (w2.referral_count > w1.referral_count
                             OR (w2.referral_count = w1.referral_count
                                 AND w2.total_rtc_earned > w1.total_rtc_earned))) as current_rank
                FROM weekly_leaderboard w1
                WHERE week_start = ? AND user_id = ?
            ''', (week_start, user_id))

            week_stats = cursor.fetchone() or (0, 0.0, 0.0, 999)

            return {
                'total_referrals': total_stats[0],
                'total_rtc_earned': total_stats[1],
                'weekly_referrals': week_stats[0],
                'weekly_rtc': week_stats[1],
                'weekly_bonus': week_stats[2],
                'current_rank': week_stats[3] if week_stats[3] < 999 else None
            }

# Flask app integration
app = Flask(__name__)
referral_system = ReferralSystem()

@app.route('/api/referral/generate', methods=['POST'])
def generate_referral():
    user_id = request.json.get('user_id')
    if not user_id:
        return jsonify({'error': 'User ID required'}), 400

    code = referral_system.get_user_referral_code(user_id)
    return jsonify({
        'referral_code': code,
        'invite_url': f"https://rustchain.ai/invite/{code}",
        'share_text': f"🚀 Join me on RustChain! Mine crypto with old hardware. Use my code: {code} for bonus RTC!"
    })

@app.route('/api/referral/process', methods=['POST'])
def process_referral():
    data = request.json
    referral_code = data.get('referral_code')
    new_user_id = data.get('user_id')
    conversion_type = data.get('type', 'signup')

    success, message = referral_system.process_referral(referral_code, new_user_id, conversion_type)

    if success:
        return jsonify({'success': True, 'message': message})
    else:
        return jsonify({'error': message}), 400

@app.route('/api/referral/stats/<user_id>')
def get_user_referral_stats(user_id):
    stats = referral_system.get_user_stats(user_id)
    return jsonify(stats)

@app.route('/api/referral/leaderboard')
def get_leaderboard():
    week_param = request.args.get('week')
    week_start = None

    if week_param:
        try:
            week_start = datetime.strptime(week_param, '%Y-%m-%d').date()
        except ValueError:
            pass

    leaderboard = referral_system.get_weekly_leaderboard(week_start)

    return jsonify({
        'week_start': str(week_start or referral_system.get_current_week_start()),
        'leaderboard': [
            {
                'rank': entry[4],
                'user_id': entry[0][:8] + '...',  # Anonymized
                'referrals': entry[1],
                'rtc_earned': entry[2],
                'bonus_rtc': entry[3] or 0
            }
            for entry in leaderboard
        ]
    })

@app.route('/invite/<referral_code>')
def referral_landing(referral_code):
    template = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Join RustChain - Invited by Friend</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { font-family: Arial; margin: 0; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }
            .container { max-width: 600px; margin: 0 auto; padding: 20px; text-align: center; }
            .hero { margin: 40px 0; }
            .hero h1 { font-size: 2.5em; margin-bottom: 20px; }
            .hero p { font-size: 1.2em; opacity: 0.9; }
            .cta-button { display: inline-block; background: #ff6b6b; color: white; padding: 15px 30px;
                         text-decoration: none; border-radius: 25px; font-size: 1.1em; margin: 20px 10px; }
            .cta-button:hover { background: #ff5252; }
            .bonus-box { background: rgba(255,255,255,0.1); border-radius: 10px; padding: 20px; margin: 20px 0; }
            .steps { text-align: left; margin: 30px 0; }
            .step { margin: 15px 0; padding: 10px; background: rgba(255,255,255,0.1); border-radius: 5px; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="hero">
                <h1>🎉 You're Invited to RustChain!</h1>
                <p>Your friend shared RustChain with you - the easiest way to mine crypto with ANY computer</p>
            </div>

            <div class="bonus-box">
                <h3>🎁 Special Invite Bonus</h3>
                <p>Get <strong>5 FREE RTC</strong> when you sign up with code: <strong>{{ referral_code }}</strong></p>
                <p>Plus earn bonus rewards for you and your friend!</p>
            </div>

            <div class="steps">
                <h3>How RustChain Works (3 Simple Steps)</h3>
                <div class="step">
                    <strong>1. Download & Install</strong> - Works on Windows, Mac, Linux (even old computers!)
                </div>
                <div class="step">
                    <strong>2. Click "Start Mining"</strong> - Automatically uses spare CPU power
                </div>
                <div class="step">
                    <strong>3. Earn RTC Daily</strong> - Get paid for contributing to the network
                </div>
            </div>

            <a href="/signup?ref={{ referral_code }}" class="cta-button">Start Mining Now - Claim Bonus</a>
            <a href="/learn-more" class="cta-button" style="background: transparent; border: 2px solid white;">Learn More First</a>

            <p style="margin-top: 40px; opacity: 0.8;">
                ✅ No technical knowledge required<br>
                ✅ Works with old hardware<br>
                ✅ Earn crypto while you sleep
            </p>
        </div>

        <script>
            // Store referral code for signup flow
            localStorage.setItem('rustchain_referral', '{{ referral_code }}');
        </script>
    </body>
    </html>
    '''

    return render_template_string(template, referral_code=referral_code)

if __name__ == '__main__':
    app.run(debug=True, port=5003)
