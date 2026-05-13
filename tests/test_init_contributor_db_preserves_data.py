# SPDX-License-Identifier: MIT

import sqlite3

import init_contributor_db


def _count_rows(db_path, table):
    with sqlite3.connect(db_path) as conn:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_init_contributor_database_is_idempotent_and_preserves_rows(tmp_path, monkeypatch):
    db_path = tmp_path / "contributors.db"
    monkeypatch.setattr(init_contributor_db, "DB_PATH", str(db_path))

    init_contributor_db.init_contributor_database()
    contributor_id = init_contributor_db.add_contributor(
        "galpetame",
        "agent",
        "RTCe4fbe4c9085b8b2ed3f1228504de66799025f6ce",
        "reviews,fixes",
    )

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO contributions (
                contributor_id, repo_name, contribution_type, description,
                rtc_earned, date_contributed, verified
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                contributor_id,
                "Scottcjn/Rustchain",
                "bugfix",
                "protect contributor initialization from destructive re-runs",
                0,
                "2026-05-13",
                True,
            ),
        )

    init_contributor_db.init_contributor_database()

    assert init_contributor_db.get_contributor_stats() == {
        "total": 1,
        "paid": 0,
        "pending": 1,
    }
    assert _count_rows(db_path, "contributors") == 1
    assert _count_rows(db_path, "contributions") == 1
    assert _count_rows(db_path, "payment_history") == 1
