# SPDX-License-Identifier: MIT

import sqlite3

import init_contributor_db as contributor_db


def table_columns(db_path, table_name):
    with sqlite3.connect(db_path) as conn:
        return {
            row[1]
            for row in conn.execute(f'PRAGMA table_info({table_name})').fetchall()
        }


def test_init_contributor_database_preserves_existing_rows(tmp_path, monkeypatch):
    db_path = tmp_path / 'contributors.db'
    monkeypatch.setattr(contributor_db, 'DB_PATH', str(db_path))

    contributor_db.init_contributor_database()
    contributor_id = contributor_db.add_contributor(
        'existing-user',
        'human',
        'RTC0123456789abcdef0123456789abcdef01234567',
        'maintainer',
    )

    contributor_db.init_contributor_database()

    with sqlite3.connect(db_path) as conn:
        contributor = conn.execute(
            'SELECT github_username, rtc_wallet FROM contributors WHERE id = ?',
            (contributor_id,),
        ).fetchone()
        payment = conn.execute(
            'SELECT amount, transaction_type FROM payment_history WHERE contributor_id = ?',
            (contributor_id,),
        ).fetchone()

    assert contributor == ('existing-user', 'RTC0123456789abcdef0123456789abcdef01234567')
    assert payment == (5.0, 'registration_bonus')


def test_init_contributor_database_migrates_legacy_contributors_table(tmp_path, monkeypatch):
    db_path = tmp_path / 'contributors.db'
    monkeypatch.setattr(contributor_db, 'DB_PATH', str(db_path))

    with sqlite3.connect(db_path) as conn:
        conn.execute('''
        CREATE TABLE contributors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            github_username TEXT UNIQUE NOT NULL,
            contributor_type TEXT NOT NULL,
            rtc_wallet TEXT NOT NULL,
            registration_date TEXT NOT NULL
        )
        ''')
        conn.execute(
            '''
            INSERT INTO contributors (github_username, contributor_type, rtc_wallet, registration_date)
            VALUES (?, ?, ?, ?)
            ''',
            ('legacy-user', 'agent', 'RTCabcdef0123456789abcdef0123456789abcdef01', '2026-05-12T00:00:00'),
        )
        conn.commit()

    contributor_db.init_contributor_database()

    columns = table_columns(db_path, 'contributors')
    assert {'roles', 'payment_status', 'created_at', 'updated_at'} <= columns

    with sqlite3.connect(db_path) as conn:
        contributor = conn.execute(
            'SELECT github_username, payment_status FROM contributors WHERE github_username = ?',
            ('legacy-user',),
        ).fetchone()
        contributions_table = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='contributions'"
        ).fetchone()
        payment_table = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='payment_history'"
        ).fetchone()

    assert contributor == ('legacy-user', 'pending')
    assert contributions_table == ('contributions',)
    assert payment_table == ('payment_history',)
