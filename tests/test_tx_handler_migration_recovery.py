# SPDX-License-Identifier: MIT
import sqlite3
import sys

import pytest


tx_handler = sys.modules["tx_handler"]


def test_recovers_balances_old_when_migration_crashed_before_new_rename(tmp_path):
    db_path = str(tmp_path / "tx_recover_old.db")
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "CREATE TABLE balances_old "
            "(wallet TEXT PRIMARY KEY, balance_urtc INTEGER NOT NULL, wallet_nonce INTEGER DEFAULT 0)"
        )
        conn.execute(
            "INSERT INTO balances_old (wallet, balance_urtc, wallet_nonce) VALUES (?, ?, ?)",
            ("alice", 1234, 7),
        )

    pool = tx_handler.TransactionPool(db_path)

    assert pool.get_balance("alice") == 1234
    assert pool.get_wallet_nonce("alice") == 7
    with sqlite3.connect(db_path) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert "balances" in tables
    assert "balances_old" not in tables


def test_completes_balances_new_when_migration_crashed_after_old_rename(tmp_path):
    db_path = str(tmp_path / "tx_recover_new.db")
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "CREATE TABLE balances_old "
            "(wallet TEXT PRIMARY KEY, balance_urtc INTEGER NOT NULL, wallet_nonce INTEGER DEFAULT 0)"
        )
        conn.execute(
            "INSERT INTO balances_old (wallet, balance_urtc, wallet_nonce) VALUES (?, ?, ?)",
            ("old-copy", 5000, 2),
        )
        conn.execute(
            "CREATE TABLE balances_new "
            "(wallet TEXT PRIMARY KEY, balance_urtc INTEGER NOT NULL CHECK(balance_urtc >= 0), "
            "wallet_nonce INTEGER DEFAULT 0)"
        )
        conn.execute(
            "INSERT INTO balances_new (wallet, balance_urtc, wallet_nonce) VALUES (?, ?, ?)",
            ("alice", 1234, 7),
        )

    pool = tx_handler.TransactionPool(db_path)

    assert pool.get_balance("alice") == 1234
    assert pool.get_wallet_nonce("alice") == 7
    assert pool.get_balance("old-copy") == 0
    with sqlite3.connect(db_path) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO balances (wallet, balance_urtc, wallet_nonce) VALUES (?, ?, ?)",
                ("negative", -1, 0),
            )
    assert "balances" in tables
    assert "balances_old" not in tables
    assert "balances_new" not in tables
