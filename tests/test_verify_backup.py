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
