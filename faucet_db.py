// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import sqlite3
import time
import threading
from contextlib import contextmanager

DB_PATH = 'faucet.db'

class FaucetDB:
    def __init__(self):
        self._lock = threading.Lock()
        self.init_database()

    @contextmanager
    def get_connection(self):
        with self._lock:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            try:
                yield conn
            finally:
                conn.close()

    def init_database(self):
        with self.get_connection() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS faucet_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    wallet_address TEXT NOT NULL,
                    github_username TEXT,
                    amount REAL NOT NULL DEFAULT 1.0,
                    status TEXT DEFAULT 'pending',
                    ip_address TEXT,
                    user_agent TEXT,
                    created_at INTEGER NOT NULL,
                    processed_at INTEGER,
                    tx_hash TEXT
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS rate_limits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    identifier TEXT NOT NULL UNIQUE,
                    last_request INTEGER NOT NULL,
                    request_count INTEGER DEFAULT 1
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS github_accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    github_id INTEGER,
                    verified_at INTEGER NOT NULL,
                    account_created TEXT,
                    public_repos INTEGER,
                    followers INTEGER
                )
            ''')

            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_requests_wallet
                ON faucet_requests(wallet_address)
            ''')

            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_requests_github
                ON faucet_requests(github_username)
            ''')

            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_requests_created
                ON faucet_requests(created_at)
            ''')

            conn.commit()

    def add_request(self, wallet_address, github_username=None, ip_address=None, user_agent=None, amount=1.0):
        with self.get_connection() as conn:
            cursor = conn.execute('''
                INSERT INTO faucet_requests
                (wallet_address, github_username, amount, ip_address, user_agent, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (wallet_address, github_username, amount, ip_address, user_agent, int(time.time())))

            conn.commit()
            return cursor.lastrowid

    def update_request_status(self, request_id, status, tx_hash=None):
        with self.get_connection() as conn:
            processed_at = int(time.time()) if status in ['completed', 'failed'] else None
            conn.execute('''
                UPDATE faucet_requests
                SET status = ?, tx_hash = ?, processed_at = ?
                WHERE id = ?
            ''', (status, tx_hash, processed_at, request_id))
            conn.commit()

    def check_rate_limit(self, identifier, limit_hours=24):
        current_time = int(time.time())
        time_limit = current_time - (limit_hours * 3600)

        with self.get_connection() as conn:
            row = conn.execute('''
                SELECT last_request, request_count
                FROM rate_limits
                WHERE identifier = ?
            ''', (identifier,)).fetchone()

            if not row:
                return True, 0

            if row['last_request'] < time_limit:
                return True, 0

            time_remaining = (row['last_request'] + (limit_hours * 3600)) - current_time
            return False, max(0, time_remaining)

    def update_rate_limit(self, identifier):
        current_time = int(time.time())

        with self.get_connection() as conn:
            conn.execute('''
                INSERT OR REPLACE INTO rate_limits (identifier, last_request, request_count)
                VALUES (?, ?, COALESCE((
                    SELECT request_count + 1
                    FROM rate_limits
                    WHERE identifier = ?
                ), 1))
            ''', (identifier, current_time, identifier))
            conn.commit()

    def verify_github_account(self, username, github_id, account_created=None, public_repos=0, followers=0):
        with self.get_connection() as conn:
            conn.execute('''
                INSERT OR REPLACE INTO github_accounts
                (username, github_id, verified_at, account_created, public_repos, followers)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (username, github_id, int(time.time()), account_created, public_repos, followers))
            conn.commit()

    def get_github_account(self, username):
        with self.get_connection() as conn:
            return conn.execute('''
                SELECT * FROM github_accounts WHERE username = ?
            ''', (username,)).fetchone()

    def get_recent_requests(self, limit=50):
        with self.get_connection() as conn:
            return conn.execute('''
                SELECT * FROM faucet_requests
                ORDER BY created_at DESC
                LIMIT ?
            ''', (limit,)).fetchall()

    def get_request_stats(self, days=7):
        since_time = int(time.time()) - (days * 24 * 3600)

        with self.get_connection() as conn:
            total = conn.execute('''
                SELECT COUNT(*) as count
                FROM faucet_requests
                WHERE created_at >= ?
            ''', (since_time,)).fetchone()['count']

            completed = conn.execute('''
                SELECT COUNT(*) as count
                FROM faucet_requests
                WHERE created_at >= ? AND status = 'completed'
            ''', (since_time,)).fetchone()['count']

            amount_distributed = conn.execute('''
                SELECT COALESCE(SUM(amount), 0) as total
                FROM faucet_requests
                WHERE created_at >= ? AND status = 'completed'
            ''', (since_time,)).fetchone()['total']

            return {
                'total_requests': total,
                'completed_requests': completed,
                'amount_distributed': amount_distributed,
                'success_rate': (completed / total * 100) if total > 0 else 0
            }

    def cleanup_old_records(self, days=30):
        cutoff_time = int(time.time()) - (days * 24 * 3600)

        with self.get_connection() as conn:
            cursor = conn.execute('''
                DELETE FROM faucet_requests
                WHERE created_at < ? AND status IN ('completed', 'failed')
            ''', (cutoff_time,))

            deleted_requests = cursor.rowcount

            conn.execute('''
                DELETE FROM rate_limits
                WHERE last_request < ?
            ''', (cutoff_time,))

            conn.commit()
            return deleted_requests
