# SPDX-License-Identifier: MIT

import os
import sys
import tempfile
import sqlite3
import pytest

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

@pytest.fixture(scope='function')
def test_db():
    """Create a temporary database for testing"""
    db_fd, db_path = tempfile.mkstemp()

    # Initialize test database with required schema
    with sqlite3.connect(db_path) as conn:
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
        ''')

    yield db_path

    # Cleanup
    os.close(db_fd)
    os.unlink(db_path)

@pytest.fixture(scope='function')
def client():
    """Create a test client for Flask app"""
    import human_funnel

    human_funnel.app.config['TESTING'] = True
    with human_funnel.app.test_client() as client:
        yield client
