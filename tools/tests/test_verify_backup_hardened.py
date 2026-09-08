# SPDX-License-Identifier: MIT
"""
Tests for verify_backup.py - RustChain SQLite backup verifier.

Covers:
- Integrity check on a healthy backup (PASS).
- Corrupted backup (FAIL).
- Missing required table (FAIL).
- Missing live DB (FAIL).
- Missing backup file (FAIL).
- Zero positive balances (FAIL).
- Epoch drift > 1 (recency FAIL).
- Epoch drift == 1 (recency PASS).
- Positive-balance column name variants.
- --json output is valid JSON.
- Gzip-decompressed backup verification.
- SHA-256 digest populated.
- latest_backup() discovery and ordering.
- Positive-balance column missing raises OperationalError.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import sqlite3
import sys
import tempfile
import textwrap

import pytest

# tools/ is on sys.path via pytest invocation:  pytest tools/
from verify_backup import (
    REQUIRED_TABLES,
    SUPPORTED_BALANCE_COLUMNS,
    CheckResult,
    latest_backup,
    parse_args,
    positive_balances,
    resolve_backup_file,
    sha256_file,
    verify,
)


# ---------------------------------------------------------------------------
# Factories: create a live + backup pair with configurable properties
# ---------------------------------------------------------------------------


def _make_db(path: str, *, balances_positive: int = 3, epoch: int = 5) -> str:
    """Create a minimal RustChain-like SQLite DB at ``path``."""
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE IF NOT EXISTS balances (id INTEGER PRIMARY KEY, amount REAL)")
    conn.execute("CREATE TABLE IF NOT EXISTS miner_attest_recent (id INTEGER PRIMARY KEY, miner TEXT, ts INTEGER)")
    conn.execute("CREATE TABLE IF NOT EXISTS headers (id INTEGER PRIMARY KEY, slot INTEGER)")
    conn.execute("CREATE TABLE IF NOT EXISTS ledger (id INTEGER PRIMARY KEY, from_addr TEXT, to_addr TEXT, amount REAL)")
    conn.execute("CREATE TABLE IF NOT EXISTS epoch_rewards (id INTEGER PRIMARY KEY, epoch INTEGER, amount REAL)")
    for i in range(balances_positive):
        conn.execute("INSERT INTO balances (amount) VALUES (?)", (10.0 + i,))
    conn.execute("INSERT INTO miner_attest_recent (miner, ts) VALUES (?, ?)", ("x", 1))
    conn.execute("INSERT INTO headers (slot) VALUES (?)", (100,))
    conn.execute("INSERT INTO ledger (from_addr, to_addr, amount) VALUES (?, ?, ?)", ("a", "b", 1.0))
    conn.execute("INSERT INTO epoch_rewards (epoch, amount) VALUES (?, ?)", (epoch, 5000.0))
    conn.commit()
    conn.close()
    return path


def _make_pair(
    tmp: str,
    *,
    live_epoch: int = 5,
    backup_epoch: int = 5,
    backup_positive: int = 3,
) -> tuple[str, str]:
    """Create a live DB and a backup DB in ``tmp`` and return their paths."""
    live = os.path.join(tmp, "live.db")
    backup = os.path.join(tmp, "rustchain_v2.db")
    _make_db(live, epoch=live_epoch)
    _make_db(backup, balances_positive=backup_positive, epoch=backup_epoch)
    return live, backup


# ---------------------------------------------------------------------------
# Integrity / correctness
# ---------------------------------------------------------------------------


def test_healthy_backup_passes():
    with tempfile.TemporaryDirectory() as tmp:
        live, backup = _make_pair(tmp)
        r = verify(live, backup)
        assert r.ok
        assert r.message == "RESULT: PASS"


def test_corrupted_backup_fails():
    with tempfile.TemporaryDirectory() as tmp:
        live, backup = _make_pair(tmp)
        # Corrupt the file by truncating its SQLite page 0.
        with open(backup, "r+b") as f:
            f.write(b"\x00" * 100)
        r = verify(live, backup)
        assert not r.ok
        assert "integrity" in r.message.lower() or "fail" in r.message.lower()


def test_missing_required_table_fails():
    with tempfile.TemporaryDirectory() as tmp:
        live, backup = _make_pair(tmp)
        conn = sqlite3.connect(backup)
        conn.execute("DROP TABLE IF EXISTS headers")
        conn.commit()
        conn.close()
        r = verify(live, backup)
        assert not r.ok
        header_check = next((c for c in r.checks if c["name"] == "headers"), None)
        assert header_check is not None
        assert header_check["ok"] is False


def test_missing_live_db_fails():
    with tempfile.TemporaryDirectory() as tmp:
        _backup = os.path.join(tmp, "rustchain_v2.db")
        _make_db(_backup)
        r = verify("/nonexistent/live.db", _backup)
        assert not r.ok
        assert "live db missing" in r.message


def test_missing_backup_file_fails():
    with tempfile.TemporaryDirectory() as tmp:
        live = os.path.join(tmp, "live.db")
        _make_db(live)
        r = verify(live, "/nonexistent/backup.db")
        assert not r.ok
        assert "backup file missing" in r.message


def test_zero_positive_balances_fails():
    with tempfile.TemporaryDirectory() as tmp:
        live, backup = _make_pair(tmp, backup_positive=0)
        r = verify(live, backup)
        assert not r.ok


def test_epoch_drift_one_passes():
    """Epoch drift of exactly 1 must be PASS (MAX_EPOCH_DRIFT == 1)."""
    with tempfile.TemporaryDirectory() as tmp:
        live, backup = _make_pair(tmp, live_epoch=6, backup_epoch=5)
        r = verify(live, backup, require_recency=True)
        assert r.ok


def test_epoch_drift_two_fails():
    """Epoch drift > 1 must be FAIL."""
    with tempfile.TemporaryDirectory() as tmp:
        live, backup = _make_pair(tmp, live_epoch=7, backup_epoch=5)
        r = verify(live, backup, require_recency=True)
        assert not r.ok
        assert r.epoch_drift == 2
        assert r.recency_ok is False


def test_no_recency_skips_epoch_check():
    with tempfile.TemporaryDirectory() as tmp:
        live, backup = _make_pair(tmp, live_epoch=7, backup_epoch=5)
        r = verify(live, backup, require_recency=False)
        assert r.ok
        assert r.recency_ok is True  # epoch check still runs; passes because drift=0


def test_sha256_is_populated():
    with tempfile.TemporaryDirectory() as tmp:
        live, backup = _make_pair(tmp)
        r = verify(live, backup)
        assert r.sha256 is not None
        assert len(r.sha256) == 64


def test_sha256_matches_file():
    with tempfile.TemporaryDirectory() as tmp:
        live, backup = _make_pair(tmp)
        expected = hashlib.sha256(open(backup, "rb").read()).hexdigest()
        r = verify(live, backup)
        assert r.sha256 == expected


# ---------------------------------------------------------------------------
# Positive-balance column variants
# ---------------------------------------------------------------------------


def _positive_balance_db(path: str, column: str) -> str:
    conn = sqlite3.connect(path)
    conn.execute(f"CREATE TABLE balances (id INTEGER PRIMARY KEY, {column} REAL)")
    conn.execute(f"CREATE TABLE miner_attest_recent (id INTEGER PRIMARY KEY)")
    conn.execute(f"CREATE TABLE headers (id INTEGER PRIMARY KEY)")
    conn.execute(f"CREATE TABLE ledger (id INTEGER PRIMARY KEY)")
    conn.execute(f"CREATE TABLE epoch_rewards (id INTEGER PRIMARY KEY, epoch INTEGER, amount REAL)")
    conn.execute(f"INSERT INTO balances ({column}) VALUES (5.0)")
    conn.execute("INSERT INTO miner_attest_recent (id) VALUES (1)")
    conn.execute("INSERT INTO headers (id) VALUES (1)")
    conn.execute("INSERT INTO ledger (id) VALUES (1)")
    conn.execute("INSERT INTO epoch_rewards (epoch, amount) VALUES (5, 100.0)")
    conn.commit()
    conn.close()
    return path


@pytest.mark.parametrize("column", SUPPORTED_BALANCE_COLUMNS)
def test_positive_balance_column_variants_pass(column: str):
    with tempfile.TemporaryDirectory() as tmp:
        live = os.path.join(tmp, "live.db")
        backup = os.path.join(tmp, "backup.db")
        _positive_balance_db(live, column)
        _positive_balance_db(backup, column)
        r = verify(live, backup, require_recency=False)
        assert r.ok


def test_positive_balance_column_missing_raises():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "db.sqlite")
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE balances (id INTEGER PRIMARY KEY)")
        conn.commit()
        conn.close()
        with pytest.raises(sqlite3.OperationalError):
            positive_balances(sqlite3.connect(path))


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


def test_latest_backup_chooses_newest():
    with tempfile.TemporaryDirectory() as tmp:
        old = os.path.join(tmp, "rustchain_v2_001.db")
        new = os.path.join(tmp, "rustchain_v2_002.db")
        _make_db(old, epoch=1)
        _make_db(new, epoch=2)
        # Ensure new is newer than old.
        os.utime(old, (1, 1))
        os.utime(new, (10000, 10000))
        assert latest_backup(tmp, "rustchain_v2*.db") == new


def test_latest_backup_none_when_empty():
    with tempfile.TemporaryDirectory() as tmp:
        assert latest_backup(tmp, "rustchain_v2*.db") is None


# ---------------------------------------------------------------------------
# Gzip support
# ---------------------------------------------------------------------------


def test_gzip_backup_is_verified():
    with tempfile.TemporaryDirectory() as tmp:
        live = os.path.join(tmp, "live.db")
        backup_plain = os.path.join(tmp, "rustchain_v2.db")
        backup_gz = os.path.join(tmp, "rustchain_v2.db.gz")
        _make_db(live)
        _make_db(backup_plain)
        with open(backup_plain, "rb") as f_in, gzip.open(backup_gz, "wb") as f_out:
            for chunk in iter(lambda: f_in.read(65536), b""):
                f_out.write(chunk)
        resolved, was_gz = resolve_backup_file(backup_gz)
        assert was_gz
        r = verify(live, resolved, require_recency=False)
        assert r.ok
        os.unlink(resolved)


def test_plain_backup_returns_same_path():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "backup.db")
        _make_db(path)
        resolved, was_gz = resolve_backup_file(path)
        assert resolved == path
        assert not was_gz


def test_gzip_missing_returns_path_unchanged():
    path = "/no/such/file.gz"
    resolved, was_gz = resolve_backup_file(path)
    assert resolved == path
    assert not was_gz


# ---------------------------------------------------------------------------
# CLI / JSON output
# ---------------------------------------------------------------------------


def test_json_output_is_valid():
    with tempfile.TemporaryDirectory() as tmp:
        live = os.path.join(tmp, "live.db")
        backup = os.path.join(tmp, "rustchain_v2.db")
        _make_db(live)
        _make_db(backup)
        # Call top-level main() via subprocess so stdout is captured cleanly.
        out = os.popen(
            f"{sys.executable} {os.path.join(os.path.dirname(__file__), '..', 'verify_backup.py')} "
            f"--live-db {live} --backup-file {backup} --json",
            "r",
        ).read()
        data = json.loads(out)
        assert "ok" in data
        assert "checks" in data
        assert data["ok"] is True


def test_help_exits_zero():
    """argparse exits with code 0 on --help (subprocess)."""
    import subprocess

    proc = subprocess.run(
        [
            sys.executable,
            os.path.join(os.path.dirname(__file__), "..", "verify_backup.py"),
            "--help",
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert "Verify latest RustChain SQLite backup integrity" in proc.stdout


# ---------------------------------------------------------------------------
# Edge: empty DB (tables exist but have 0 rows) should FAIL row-count check
# ---------------------------------------------------------------------------


def test_empty_backup_fails():
    with tempfile.TemporaryDirectory() as tmp:
        live = os.path.join(tmp, "live.db")
        backup = os.path.join(tmp, "backup.db")
        _make_db(live)
        conn = sqlite3.connect(backup)
        conn.executescript(textwrap.dedent("""
            CREATE TABLE balances (id INTEGER PRIMARY KEY, amount REAL);
            CREATE TABLE miner_attest_recent (id INTEGER PRIMARY KEY);
            CREATE TABLE headers (id INTEGER PRIMARY KEY);
            CREATE TABLE ledger (id INTEGER PRIMARY KEY);
            CREATE TABLE epoch_rewards (id INTEGER PRIMARY KEY, epoch INTEGER, amount REAL);
        """))
        conn.commit()
        conn.close()
        r = verify(live, backup, require_recency=False)
        assert not r.ok
