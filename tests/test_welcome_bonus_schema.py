# SPDX-License-Identifier: MIT

import sqlite3

import integrated_node


TRUSTED = {"state": "trusted"}


def _graduate(db_path, miner):
    """sybil_guard: the bonus is paid at probation exit, authorised from the
    persisted miner_probation row. Persist a graduated (trusted) row."""
    integrated_node.sybil_guard.init_schema(str(db_path))
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO miner_probation (miner, state, first_seen, last_seen, updated_at) "
            "VALUES (?, 'trusted', 1, 1, 1)", (miner,))


def _create_history(conn, miner="miner_welcome"):
    conn.execute("CREATE TABLE miner_attest_history (miner TEXT NOT NULL)")
    conn.execute("INSERT INTO miner_attest_history (miner) VALUES (?)", (miner,))


def test_welcome_bonus_credits_current_account_ledger_schema(tmp_path, monkeypatch):
    db_path = tmp_path / "account-ledger.db"
    miner = "miner_welcome"
    bonus_i64 = int(integrated_node.WELCOME_BONUS_RTC * 1_000_000)

    with sqlite3.connect(db_path) as conn:
        _create_history(conn, miner)
        conn.execute(
            """
            CREATE TABLE balances (
                miner_id TEXT PRIMARY KEY,
                amount_i64 INTEGER NOT NULL DEFAULT 0,
                balance_rtc REAL NOT NULL DEFAULT 0
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE ledger (
                ts INTEGER NOT NULL,
                epoch INTEGER NOT NULL,
                miner_id TEXT NOT NULL,
                delta_i64 INTEGER NOT NULL,
                reason TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "INSERT INTO balances (miner_id, amount_i64, balance_rtc) VALUES (?, ?, ?)",
            (integrated_node.WELCOME_BONUS_SOURCE, bonus_i64 * 2, integrated_node.WELCOME_BONUS_RTC * 2),
        )
        conn.commit()

    monkeypatch.setattr(integrated_node, "DB_PATH", str(db_path))
    _graduate(db_path, miner)
    monkeypatch.setattr(integrated_node, "current_slot", lambda: 144 * 7)
    monkeypatch.setattr(integrated_node, "slot_to_epoch", lambda slot: slot // 144)

    integrated_node._check_welcome_bonus(miner, TRUSTED)

    with sqlite3.connect(db_path) as conn:
        balances = dict(conn.execute("SELECT miner_id, amount_i64 FROM balances").fetchall())
        assert balances[integrated_node.WELCOME_BONUS_SOURCE] == bonus_i64
        assert balances[miner] == bonus_i64

        ledger_rows = conn.execute(
            "SELECT epoch, miner_id, delta_i64, reason FROM ledger ORDER BY delta_i64"
        ).fetchall()
        assert ledger_rows == [
            (7, integrated_node.WELCOME_BONUS_SOURCE, -bonus_i64, f"welcome_bonus:{integrated_node.WELCOME_BONUS_RTC}_rtc"),
            (7, miner, bonus_i64, f"welcome_bonus:{integrated_node.WELCOME_BONUS_RTC}_rtc"),
        ]

    integrated_node._check_welcome_bonus(miner, TRUSTED)

    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM ledger").fetchone()[0] == 2
        balances = dict(conn.execute("SELECT miner_id, amount_i64 FROM balances").fetchall())
        assert balances[integrated_node.WELCOME_BONUS_SOURCE] == bonus_i64
        assert balances[miner] == bonus_i64


def test_welcome_bonus_keeps_legacy_transfer_ledger_schema(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy-ledger.db"
    miner = "miner_legacy"
    bonus_i64 = int(integrated_node.WELCOME_BONUS_RTC * 1_000_000)

    with sqlite3.connect(db_path) as conn:
        _create_history(conn, miner)
        conn.execute(
            "CREATE TABLE balances (miner_id TEXT PRIMARY KEY, amount_i64 INTEGER NOT NULL DEFAULT 0)"
        )
        conn.execute(
            """
            CREATE TABLE ledger (
                from_miner TEXT NOT NULL,
                to_miner TEXT NOT NULL,
                amount_i64 INTEGER NOT NULL,
                memo TEXT NOT NULL,
                ts INTEGER NOT NULL
            )
            """
        )
        conn.execute(
            "INSERT INTO balances (miner_id, amount_i64) VALUES (?, ?)",
            (integrated_node.WELCOME_BONUS_SOURCE, bonus_i64 * 2),
        )
        conn.commit()

    monkeypatch.setattr(integrated_node, "DB_PATH", str(db_path))
    _graduate(db_path, miner)

    integrated_node._check_welcome_bonus(miner, TRUSTED)

    with sqlite3.connect(db_path) as conn:
        balances = dict(conn.execute("SELECT miner_id, amount_i64 FROM balances").fetchall())
        assert balances[integrated_node.WELCOME_BONUS_SOURCE] == bonus_i64
        assert balances[miner] == bonus_i64

        row = conn.execute(
            "SELECT from_miner, to_miner, amount_i64, memo FROM ledger"
        ).fetchone()
        assert row == (
            integrated_node.WELCOME_BONUS_SOURCE,
            miner,
            bonus_i64,
            f"welcome_bonus:{integrated_node.WELCOME_BONUS_RTC}_rtc",
        )
