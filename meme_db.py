// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import sqlite3
import os
import hashlib
import json
from datetime import datetime

DB_PATH = 'meme_contest.db'

class MemeDB:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self.init_database()

    def init_database(self):
        """Initialize database tables for meme contest"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Users table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    wallet_address TEXT,
                    submission_count INTEGER DEFAULT 0,
                    total_rtc_earned REAL DEFAULT 0.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Memes table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS memes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    title TEXT NOT NULL,
                    description TEXT,
                    file_path TEXT NOT NULL,
                    file_hash TEXT UNIQUE NOT NULL,
                    file_size INTEGER,
                    image_format TEXT,
                    width INTEGER,
                    height INTEGER,
                    status TEXT DEFAULT 'pending',
                    rtc_reward REAL DEFAULT 0.0,
                    admin_notes TEXT,
                    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    reviewed_at TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
            
            # Votes table for community voting
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS votes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    meme_id INTEGER,
                    user_id INTEGER,
                    vote_type TEXT CHECK(vote_type IN ('up', 'down', 'top3')),
                    voted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (meme_id) REFERENCES memes (id),
                    FOREIGN KEY (user_id) REFERENCES users (id),
                    UNIQUE(meme_id, user_id, vote_type)
                )
            ''')
            
            # Contest metadata
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS contest_config (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Initialize contest settings
            cursor.execute('''
                INSERT OR IGNORE INTO contest_config (key, value) VALUES
                ('max_submissions_per_user', '5'),
                ('base_rtc_reward', '1.0'),
                ('top3_rtc_reward', '3.0'),
                ('contest_active', 'true'),
                ('min_image_width', '500')
            ''')
            
            conn.commit()

    def add_user(self, username, wallet_address=None):
        """Add new user to contest"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('''
                    INSERT INTO users (username, wallet_address) 
                    VALUES (?, ?)
                ''', (username, wallet_address))
                conn.commit()
                return cursor.lastrowid
            except sqlite3.IntegrityError:
                return None

    def get_user(self, username):
        """Get user by username"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
            return cursor.fetchone()

    def submit_meme(self, username, title, description, file_path, file_hash, 
                   file_size, image_format, width, height):
        """Submit new meme to contest"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Get user
            user = self.get_user(username)
            if not user:
                return None
                
            user_id = user[0]
            current_submissions = user[3]
            
            # Check submission limit
            if current_submissions >= 5:
                return {'error': 'Maximum 5 submissions per user'}
            
            # Check image requirements
            if width < 500:
                return {'error': 'Image must be at least 500px wide'}
                
            try:
                cursor.execute('''
                    INSERT INTO memes 
                    (user_id, title, description, file_path, file_hash, 
                     file_size, image_format, width, height) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (user_id, title, description, file_path, file_hash,
                      file_size, image_format, width, height))
                
                # Update user submission count
                cursor.execute('''
                    UPDATE users SET submission_count = submission_count + 1 
                    WHERE id = ?
                ''', (user_id,))
                
                conn.commit()
                return {'meme_id': cursor.lastrowid, 'status': 'submitted'}
                
            except sqlite3.IntegrityError:
                return {'error': 'Duplicate meme detected'}

    def get_pending_memes(self):
        """Get all memes pending review"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT m.*, u.username FROM memes m
                JOIN users u ON m.user_id = u.id
                WHERE m.status = 'pending'
                ORDER BY m.submitted_at ASC
            ''')
            return cursor.fetchall()

    def approve_meme(self, meme_id, rtc_reward=1.0, admin_notes=''):
        """Approve meme and assign RTC reward"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE memes SET 
                status = 'approved', 
                rtc_reward = ?, 
                admin_notes = ?,
                reviewed_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (rtc_reward, admin_notes, meme_id))
            
            # Update user total earnings
            cursor.execute('''
                UPDATE users SET total_rtc_earned = total_rtc_earned + ?
                WHERE id = (SELECT user_id FROM memes WHERE id = ?)
            ''', (rtc_reward, meme_id))
            
            conn.commit()
            return cursor.rowcount > 0

    def reject_meme(self, meme_id, admin_notes=''):
        """Reject meme submission"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE memes SET 
                status = 'rejected', 
                admin_notes = ?,
                reviewed_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (admin_notes, meme_id))
            conn.commit()
            return cursor.rowcount > 0

    def cast_vote(self, meme_id, username, vote_type='up'):
        """Cast vote for meme"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            user = self.get_user(username)
            if not user:
                return False
                
            try:
                cursor.execute('''
                    INSERT INTO votes (meme_id, user_id, vote_type)
                    VALUES (?, ?, ?)
                ''', (meme_id, user[0], vote_type))
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                # User already voted, update vote
                cursor.execute('''
                    UPDATE votes SET vote_type = ?, voted_at = CURRENT_TIMESTAMP
                    WHERE meme_id = ? AND user_id = ?
                ''', (vote_type, meme_id, user[0]))
                conn.commit()
                return True

    def get_meme_votes(self, meme_id):
        """Get vote counts for meme"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT vote_type, COUNT(*) FROM votes 
                WHERE meme_id = ? 
                GROUP BY vote_type
            ''', (meme_id,))
            votes = dict(cursor.fetchall())
            return {
                'up': votes.get('up', 0),
                'down': votes.get('down', 0),
                'top3': votes.get('top3', 0)
            }

    def get_leaderboard(self):
        """Get meme contest leaderboard"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT u.username, u.submission_count, u.total_rtc_earned,
                       COUNT(m.id) as approved_memes
                FROM users u
                LEFT JOIN memes m ON u.id = m.user_id AND m.status = 'approved'
                WHERE u.submission_count > 0
                GROUP BY u.id
                ORDER BY u.total_rtc_earned DESC, approved_memes DESC
            ''')
            return cursor.fetchall()

    def get_public_memes(self):
        """Get approved memes for public display"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT m.id, m.title, m.description, m.file_path, 
                       m.rtc_reward, m.submitted_at, u.username
                FROM memes m
                JOIN users u ON m.user_id = u.id
                WHERE m.status = 'approved'
                ORDER BY m.rtc_reward DESC, m.submitted_at DESC
            ''')
            return cursor.fetchall()

    def calculate_file_hash(self, file_path):
        """Calculate SHA-256 hash of uploaded file"""
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()

    def get_contest_stats(self):
        """Get overall contest statistics"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            stats = {}
            cursor.execute('SELECT COUNT(*) FROM memes')
            stats['total_submissions'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM memes WHERE status = 'approved'")
            stats['approved_memes'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM memes WHERE status = 'pending'")
            stats['pending_review'] = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(DISTINCT user_id) FROM memes')
            stats['participating_users'] = cursor.fetchone()[0]
            
            cursor.execute('SELECT SUM(rtc_reward) FROM memes WHERE status = "approved"')
            total_rewards = cursor.fetchone()[0]
            stats['total_rtc_distributed'] = total_rewards if total_rewards else 0.0
            
            return stats

if __name__ == '__main__':
    # Initialize database
    db = MemeDB()
    print("Meme contest database initialized successfully!")
    
    # Print stats
    stats = db.get_contest_stats()
    print(f"Current stats: {stats}")