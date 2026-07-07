# SPDX-License-Identifier: MIT
"""Unit tests for the canonical encumbrance reader (node/available_balance.py).

This is the single source of truth that withdrawal and governance subtract from
their balance reads so reserved funds can't be drained from under a pending op.
"""
import importlib.util
import sqlite3
import sys
import time
from pathlib import Path

import pytest

NODE = Path(__file__).resolve().parents[1] / "node"


def _load_encumbered():
    sys.path.insert(0, str(NODE))
    spec = importlib.util.spec_from_file_location(
        "available_balance_under_test", NODE / "available_balance.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.encumbered_i64


encumbered_i64 = _load_encumbered()


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.execute("""CREATE TABLE pending_ledger (
        id INTEGER PRIMARY KEY AUTOINCREMENT, from_miner TEXT, to_miner TEXT,
        amount_i64 INTEGER, status TEXT DEFAULT 'pending')""")
    conn.execute("""CREATE TABLE bridge_transfers (
        id INTEGER PRIMARY KEY AUTOINCREMENT, direction TEXT, source_address TEXT,
        amount_i64 INTEGER, status TEXT, source_debited INTEGER DEFAULT 0)""")
    conn.commit()
    return conn

W = "RTCwallet"


def _pending(conn, amt, status="pending", who=W):
    conn.execute("INSERT INTO pending_ledger (from_miner, to_miner, amount_i64, status) "
                 "VALUES (?, 'x', ?, ?)", (who, amt, status))
    conn.commit()


def _deposit(conn, amt, status="locked", source_debited=0, who=W):
    conn.execute("INSERT INTO bridge_transfers (direction, source_address, amount_i64, status, source_debited) "
                 "VALUES ('deposit', ?, ?, ?, ?)", (who, amt, status, source_debited))
    conn.commit()


def test_zero_when_nothing_reserved(db):
    assert encumbered_i64(db, W) == 0


def test_missing_tables_returns_zero():
    conn = sqlite3.connect(":memory:")  # no tables at all
    assert encumbered_i64(conn, W) == 0


def test_pending_transfer_counted(db):
    _pending(db, 90)
    assert encumbered_i64(db, W) == 90


def test_non_pending_transfer_not_counted(db):
    _pending(db, 50, status="confirmed")
    _pending(db, 30, status="voided")
    assert encumbered_i64(db, W) == 0


def test_undebited_bridge_deposit_counted(db):
    # Legacy / in-flight deposit not yet hard-debited.
    _deposit(db, 40, status="locked", source_debited=0)
    assert encumbered_i64(db, W) == 40


def test_hard_debited_bridge_deposit_not_double_counted(db):
    # Debit-on-lock: already left amount_i64, must NOT be subtracted again.
    _deposit(db, 40, status="confirming", source_debited=1)
    assert encumbered_i64(db, W) == 0


def test_finalized_bridge_deposit_not_counted(db):
    _deposit(db, 40, status="completed", source_debited=0)
    _deposit(db, 25, status="voided", source_debited=0)
    assert encumbered_i64(db, W) == 0


def test_real_db_error_propagates_fail_closed():
    # A non-schema OperationalError (e.g. "database is locked") must NOT be
    # swallowed — it propagates so the debit gate aborts instead of treating
    # reserved funds as spendable (fail closed, not fail open).
    class BoomCursor:
        def execute(self, *a, **k):
            raise sqlite3.OperationalError("database is locked")

    with pytest.raises(sqlite3.OperationalError):
        encumbered_i64(BoomCursor(), W)


def test_confirming_transfer_counted(db):
    # Defensive: an in-flight confirm (status 'confirming') is still encumbered.
    _pending(db, 70, status="confirming")
    assert encumbered_i64(db, W) == 70


def test_bridge_without_source_debited_column_counts_all_active():
    # Legacy bridge schema (pre debit-on-lock): no source_debited column. NONE
    # are debited yet, so all active deposits must be counted, not treated as 0.
    conn = sqlite3.connect(":memory:")
    conn.execute("""CREATE TABLE bridge_transfers (
        id INTEGER PRIMARY KEY AUTOINCREMENT, direction TEXT, source_address TEXT,
        amount_i64 INTEGER, status TEXT)""")  # no source_debited
    conn.execute("INSERT INTO bridge_transfers (direction, source_address, amount_i64, status) "
                 "VALUES ('deposit', ?, ?, 'locked')", (W, 60))
    conn.commit()
    assert encumbered_i64(conn, W) == 60


def test_sum_across_sources_and_scoped_to_wallet(db):
    _pending(db, 90)
    _deposit(db, 40, status="locked", source_debited=0)
    _pending(db, 1000, who="other_wallet")          # different wallet, ignored
    _deposit(db, 500, who="other_wallet")           # different wallet, ignored
    assert encumbered_i64(db, W) == 130
    assert encumbered_i64(db, "other_wallet") == 1500
