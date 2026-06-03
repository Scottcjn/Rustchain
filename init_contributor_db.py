# SPDX-License-Identifier: MIT

import sqlite3
from datetime import datetime

DB_PATH = 'contributors.db'


CONTRIBUTOR_COLUMN_MIGRATIONS = {
    'roles': "TEXT DEFAULT ''",
    'payment_status': "TEXT DEFAULT 'pending'",
    'created_at': "TEXT DEFAULT ''",
    'updated_at': "TEXT DEFAULT ''",
}


def _existing_columns(cursor, table_name):
    cursor.execute(f'PRAGMA table_info({table_name})')
    return {row[1] for row in cursor.fetchall()}


def _ensure_contributor_columns(cursor):
    columns = _existing_columns(cursor, 'contributors')
    for column_name, column_definition in CONTRIBUTOR_COLUMN_MIGRATIONS.items():
        if column_name not in columns:
            cursor.execute(f'ALTER TABLE contributors ADD COLUMN {column_name} {column_definition}')


def init_contributor_database():
    """Initialize the contributors database with proper schema"""

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        # Create contributors table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS contributors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            github_username TEXT UNIQUE NOT NULL,
            contributor_type TEXT NOT NULL CHECK (contributor_type IN ('human', 'bot', 'agent')),
            rtc_wallet TEXT NOT NULL,
            roles TEXT DEFAULT '',
            registration_date TEXT NOT NULL,
            payment_status TEXT DEFAULT 'pending' CHECK (payment_status IN ('pending', 'paid', 'failed')),
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        _ensure_contributor_columns(cursor)

        # Create index for faster lookups
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_github_username ON contributors(github_username)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_payment_status ON contributors(payment_status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_registration_date ON contributors(registration_date)')

        # Create contributions tracking table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS contributions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            contributor_id INTEGER NOT NULL,
            repo_name TEXT NOT NULL,
            contribution_type TEXT NOT NULL,
            description TEXT DEFAULT '',
            rtc_earned REAL DEFAULT 0,
            date_contributed TEXT NOT NULL,
            verified BOOLEAN DEFAULT FALSE,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (contributor_id) REFERENCES contributors (id) ON DELETE CASCADE
        )
        ''')

        # Create payment history table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS payment_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            contributor_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            transaction_type TEXT NOT NULL DEFAULT 'registration_bonus',
            transaction_hash TEXT DEFAULT '',
            status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'confirmed', 'failed')),
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (contributor_id) REFERENCES contributors (id) ON DELETE CASCADE
        )
        ''')

        conn.commit()
        print(f"Database initialized successfully at {DB_PATH}")

def add_contributor(github_username, contributor_type, rtc_wallet, roles=''):
    """Add a new contributor to the database"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        registration_date = datetime.now().isoformat()

        try:
            cursor.execute('''
            INSERT INTO contributors (github_username, contributor_type, rtc_wallet, roles, registration_date)
            VALUES (?, ?, ?, ?, ?)
            ''', (github_username, contributor_type, rtc_wallet, roles, registration_date))

            contributor_id = cursor.lastrowid

            # Add initial registration payment record
            cursor.execute('''
            INSERT INTO payment_history (contributor_id, amount, transaction_type)
            VALUES (?, 5.0, 'registration_bonus')
            ''', (contributor_id,))

            conn.commit()
            print(f"Added contributor {github_username} with ID {contributor_id}")
            return contributor_id

        except sqlite3.IntegrityError:
            print(f"Error: Contributor {github_username} already exists")
            return None

def get_contributor_stats():
    """Get basic statistics about contributors"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        cursor.execute('SELECT COUNT(*) FROM contributors')
        total = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM contributors WHERE payment_status = "paid"')
        paid = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM contributors WHERE payment_status = "pending"')
        pending = cursor.fetchone()[0]

        return {'total': total, 'paid': paid, 'pending': pending}

if __name__ == '__main__':
    init_contributor_database()

    # Add some test data
    test_contributors = [
        ('scottcjn', 'human', 'RTC_wallet_example_123', 'maintainer,founder'),
        ('test_bot', 'bot', 'RTC_wallet_bot_456', 'automation'),
        ('ai_agent', 'agent', 'RTC_wallet_agent_789', 'analysis')
    ]

    for username, ctype, wallet, roles in test_contributors:
        add_contributor(username, ctype, wallet, roles)

    stats = get_contributor_stats()
    print(f"Database stats: {stats}")
