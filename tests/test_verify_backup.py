# SPDX-License-Identifier: MIT

from __future__ import annotations

import sqlite3
from pathlib import Path

from tools.verify_backup import verify


def _make_db(path: Path, rows: int = 3, epoch: int = 10):
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE balances(amount REAL)")
    conn.execute("CREATE TABLE miner_attest_recent(id INTEGER)")
    conn.execute("CREATE TABLE headers(id INTEGER)")
    conn.execute("CREATE TABLE ledger(id INTEGER)")
    conn.execute("CREATE TABLE epoch_rewards(epoch INTEGER)")

    for _ in range(rows):
        conn.execute("INSERT INTO balances(amount) VALUES (1.0)")
        conn.execute("INSERT INTO miner_attest_recent(id) VALUES (1)")
        conn.execute("INSERT INTO headers(id) VALUES (1)")
        conn.execute("INSERT INTO ledger(id) VALUES (1)")
    conn.execute("INSERT INTO epoch_rewards(epoch) VALUES (?)", (epoch,))
    conn.commit()
    conn.close()


def _make_db_with_balance_column(path: Path, column: str):
    conn = sqlite3.connect(path)
    conn.execute(f"CREATE TABLE balances({column} REAL)")
    conn.execute("CREATE TABLE miner_attest_recent(id INTEGER)")
    conn.execute("CREATE TABLE headers(id INTEGER)")
    conn.execute("CREATE TABLE ledger(id INTEGER)")
    conn.execute("CREATE TABLE epoch_rewards(epoch INTEGER)")

    conn.execute(f"INSERT INTO balances({column}) VALUES (1.0)")
    conn.execute("INSERT INTO miner_attest_recent(id) VALUES (1)")
    conn.execute("INSERT INTO headers(id) VALUES (1)")
    conn.execute("INSERT INTO ledger(id) VALUES (1)")
    conn.execute("INSERT INTO epoch_rewards(epoch) VALUES (10)")
    conn.commit()
    conn.close()


def test_verify_pass(tmp_path):
    live = tmp_path / "live.db"
    bak = tmp_path / "bak.db"
    _make_db(live, rows=5, epoch=10)
    _make_db(bak, rows=5, epoch=10)

    result = verify(str(live), str(bak))
    assert result.ok is True
    assert any("RESULT: PASS" in line for line in result.lines)


def test_verify_fail_when_epoch_too_old(tmp_path):
    live = tmp_path / "live.db"
    bak = tmp_path / "bak.db"
    _make_db(live, rows=5, epoch=10)
    _make_db(bak, rows=5, epoch=7)

    result = verify(str(live), str(bak))
    assert result.ok is False
    assert any("RESULT: FAIL" in line for line in result.lines)


def test_verify_reports_missing_table_without_crashing(tmp_path):
    live = tmp_path / "live.db"
    bak = tmp_path / "bak.db"
    _make_db(live, rows=1, epoch=10)

    conn = sqlite3.connect(bak)
    conn.execute("CREATE TABLE balances(amount REAL)")
    conn.execute("INSERT INTO balances(amount) VALUES (1.0)")
    conn.commit()
    conn.close()

    result = verify(str(live), str(bak))
    assert result.ok is False
    assert any("miner_attest_recent: missing in backup" in line for line in result.lines)
    assert any("RESULT: FAIL" in line for line in result.lines)


def test_verify_accepts_balance_rtc_column(tmp_path):
    live = tmp_path / "live.db"
    bak = tmp_path / "bak.db"
    _make_db_with_balance_column(live, "balance_rtc")
    _make_db_with_balance_column(bak, "balance_rtc")

    result = verify(str(live), str(bak))
    assert result.ok is True
    assert any("balances (amount>0): 1" in line for line in result.lines)


def test_verify_returns_failed_check_result_when_backup_missing(tmp_path):
    """Regression: verify() must not raise when backup file disappears before copy2()."""
    live = tmp_path / "live.db"
    bak = tmp_path / "bak.db"
    _make_db(live, rows=3, epoch=10)
    # bak does not exist on disk

    result = verify(str(live), str(bak))
    assert result.ok is False
    assert any("backup file missing" in line for line in result.lines)
    assert any("RESULT: FAIL" in line for line in result.lines)
