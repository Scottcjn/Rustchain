# SPDX-License-Identifier: MIT
"""Regression tests for contributor database helper functions."""

import importlib.util
import sqlite3
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "init_contributor_db.py"
spec = importlib.util.spec_from_file_location("init_contributor_db", MODULE_PATH)
contrib_db = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(contrib_db)


def test_init_contributor_database_creates_expected_tables_and_indexes(tmp_path, monkeypatch):
    db_path = tmp_path / "contributors.db"
    monkeypatch.setattr(contrib_db, "DB_PATH", str(db_path))

    contrib_db.init_contributor_database()

    with sqlite3.connect(db_path) as conn:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        indexes = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}

    assert {"contributors", "contributions", "payment_history"}.issubset(tables)
    assert {"idx_github_username", "idx_payment_status", "idx_registration_date"}.issubset(indexes)


def test_add_contributor_records_contributor_and_registration_bonus(tmp_path, monkeypatch):
    db_path = tmp_path / "contributors.db"
    monkeypatch.setattr(contrib_db, "DB_PATH", str(db_path))
    contrib_db.init_contributor_database()

    contributor_id = contrib_db.add_contributor("alice", "human", "RTC_alice", "tester")

    assert contributor_id == 1
    with sqlite3.connect(db_path) as conn:
        contributor = conn.execute(
            "SELECT github_username, contributor_type, rtc_wallet, roles, payment_status FROM contributors"
        ).fetchone()
        payment = conn.execute(
            "SELECT contributor_id, amount, transaction_type, status FROM payment_history"
        ).fetchone()

    assert contributor == ("alice", "human", "RTC_alice", "tester", "pending")
    assert payment == (1, 5.0, "registration_bonus", "pending")


def test_duplicate_contributor_is_rejected_without_second_bonus(tmp_path, monkeypatch):
    db_path = tmp_path / "contributors.db"
    monkeypatch.setattr(contrib_db, "DB_PATH", str(db_path))
    contrib_db.init_contributor_database()

    assert contrib_db.add_contributor("alice", "human", "RTC_alice") == 1
    assert contrib_db.add_contributor("alice", "human", "RTC_other") is None

    with sqlite3.connect(db_path) as conn:
        contributor_count = conn.execute("SELECT COUNT(*) FROM contributors").fetchone()[0]
        payment_count = conn.execute("SELECT COUNT(*) FROM payment_history").fetchone()[0]

    assert contributor_count == 1
    assert payment_count == 1


def test_get_contributor_stats_counts_payment_states(tmp_path, monkeypatch):
    db_path = tmp_path / "contributors.db"
    monkeypatch.setattr(contrib_db, "DB_PATH", str(db_path))
    contrib_db.init_contributor_database()
    contrib_db.add_contributor("alice", "human", "RTC_alice")
    contrib_db.add_contributor("botty", "bot", "RTC_bot")

    with sqlite3.connect(db_path) as conn:
        conn.execute("UPDATE contributors SET payment_status = 'paid' WHERE github_username = 'alice'")
        conn.commit()

    assert contrib_db.get_contributor_stats() == {"total": 2, "paid": 1, "pending": 1}
