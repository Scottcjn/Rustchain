#!/usr/bin/env python3
"""Tests for expire_confirmed_bridge_transfers — issue #6416 fix.

Covers:
 - Expired locks are transitioned to 'failed' and refunded
 - Non-expired locks are untouched
 - Already-failed transfers are skipped
 - Deposit direction refunds the source wallet
 - Withdraw direction refunds without balance credit
"""

from __future__ import annotations

import os
import sqlite3
import sys
import time
import tempfile

import pytest

sys.path.insert(0, "node")

import bridge_api as ba
from bridge_api import (
    expire_confirmed_bridge_transfers,
    init_bridge_schema,
    BridgeTransferRequest,
)

_UNSET = object()  # sentinel for _insert_transfer default


@pytest.fixture
def db():
    """Create an in-memory SQLite database with bridge + lock + balance schemas."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    init_bridge_schema(cur)
    # Also create lock_ledger and balances tables
    cur.execute("""
        CREATE TABLE IF NOT EXISTS lock_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bridge_transfer_id INTEGER NOT NULL,
            miner_id TEXT NOT NULL,
            amount_i64 INTEGER NOT NULL,
            lock_type TEXT NOT NULL,
            locked_at INTEGER NOT NULL,
            unlock_at INTEGER,
            unlocked_at INTEGER,
            released_by TEXT,
            status TEXT NOT NULL DEFAULT 'locked',
            created_at INTEGER NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS balances (
            miner_id TEXT PRIMARY KEY,
            amount_i64 INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.commit()
    yield conn
    conn.close()


def _insert_transfer(conn, *, bridge_id=1, direction="deposit", status="locked",
                      source="RTC" + "A" * 40, dest="SolAddr" * 5,
                      amount_i64=1_000_000, amount_rtc=1.0,
                      expires_at=_UNSET, tx_hash=None):
    """Helper to insert a bridge transfer + optional lock ledger entry."""
    now = int(time.time())
    if tx_hash is None:
        tx_hash = f"tx_{bridge_id}"
    # Default: expired by 100 seconds. Pass expires_at=None explicitly for NULL.
    if expires_at is _UNSET:
        expires_at = now - 100

    conn.execute(
        """INSERT INTO bridge_transfers
           (id, direction, source_chain, dest_chain, source_address, dest_address,
            amount_i64, amount_rtc, bridge_type, status, lock_epoch,
            created_at, updated_at, expires_at, tx_hash)
           VALUES (?, ?, 'rustchain', 'solana', ?, ?,
                   ?, ?, 'bottube', ?, 1,
                   ?, ?, ?, ?)""",
        (bridge_id, direction, source, dest,
         amount_i64, amount_rtc, status,
         now, now, expires_at, tx_hash)
    )

    if status in ("locked", "confirming"):
        conn.execute(
            """INSERT INTO lock_ledger
               (bridge_transfer_id, miner_id, amount_i64, lock_type,
                locked_at, unlock_at, status, created_at)
               VALUES (?, ?, ?, 'bridge_deposit', ?, ?, 'locked', ?)""",
            (bridge_id, source, amount_i64, now, expires_at, now)
        )

    conn.commit()


class TestExpireConfirmedBridgeTransfers:
    """Tests for expire_confirmed_bridge_transfers (#6416)."""

    def test_expired_locked_transfer_is_failed(self, db):
        """A locked transfer past its expiry should transition to 'failed'."""
        _insert_transfer(db, bridge_id=10, status="locked", expires_at=int(time.time()) - 1)

        count, expired = expire_confirmed_bridge_transfers(db)
        assert count == 1
        assert expired[0]["bridge_id"] == 10

        row = db.execute("SELECT status, failure_reason FROM bridge_transfers WHERE id=10").fetchone()
        assert row["status"] == "failed"
        assert row["failure_reason"] == "lock_expired_before_release"

    def test_expired_confirming_transfer_is_failed(self, db):
        """A confirming transfer past its expiry should also be recovered."""
        _insert_transfer(db, bridge_id=20, status="confirming", expires_at=int(time.time()) - 1)

        count, expired = expire_confirmed_bridge_transfers(db)
        assert count == 1

        row = db.execute("SELECT status FROM bridge_transfers WHERE id=20").fetchone()
        assert row["status"] == "failed"

    def test_non_expired_transfer_untouched(self, db):
        """A locked transfer not yet expired should NOT be transitioned."""
        _insert_transfer(db, bridge_id=30, status="locked", expires_at=int(time.time()) + 9999)

        count, _ = expire_confirmed_bridge_transfers(db)
        assert count == 0

        row = db.execute("SELECT status FROM bridge_transfers WHERE id=30").fetchone()
        assert row["status"] == "locked"

    def test_completed_transfer_untouched(self, db):
        """A completed transfer should never be expired even if past TTL."""
        _insert_transfer(db, bridge_id=40, status="completed", expires_at=int(time.time()) - 1)

        count, _ = expire_confirmed_bridge_transfers(db)
        assert count == 0

    def test_deposit_refunds_source_wallet(self, db):
        """Deposit direction: source wallet should be credited back."""
        source = "RTC" + "B" * 40
        _insert_transfer(db, bridge_id=50, direction="deposit", source=source,
                         amount_i64=5_000_000, expires_at=int(time.time()) - 1)

        # Pre-seed the balance
        db.execute("INSERT INTO balances (miner_id, amount_i64) VALUES (?, 1000)", (source,))
        db.commit()

        expire_confirmed_bridge_transfers(db)

        row = db.execute("SELECT amount_i64 FROM balances WHERE miner_id=?", (source,)).fetchone()
        assert row["amount_i64"] == 5_001_000

    def test_lock_ledger_released(self, db):
        """The lock_ledger entry should be marked as 'released'."""
        _insert_transfer(db, bridge_id=60, status="locked", expires_at=int(time.time()) - 1)

        expire_confirmed_bridge_transfers(db)

        row = db.execute("SELECT status, released_by FROM lock_ledger WHERE bridge_transfer_id=60").fetchone()
        assert row["status"] == "released"
        assert row["released_by"] == "expire_refund"

    def test_limit_respected(self, db):
        """The limit parameter should cap how many transfers are expired."""
        now = int(time.time())
        for i in range(5):
            _insert_transfer(db, bridge_id=100 + i, status="locked", expires_at=now - 1,
                             tx_hash=f"tx_limit_{i}")

        count, _ = expire_confirmed_bridge_transfers(db, limit=2)
        assert count == 2

    def test_no_expires_at_skipped(self, db):
        """Transfers with NULL expires_at should not be expired."""
        _insert_transfer(db, bridge_id=70, status="locked", expires_at=None)

        count, _ = expire_confirmed_bridge_transfers(db)
        assert count == 0

    def test_withdraw_no_balance_credit(self, db):
        """Withdraw direction: no balance credit (only lock_ledger release)."""
        source = "RTC" + "C" * 40
        _insert_transfer(db, bridge_id=80, direction="withdraw", source=source,
                         amount_i64=3_000_000, expires_at=int(time.time()) - 1)

        count, expired = expire_confirmed_bridge_transfers(db)
        assert count == 1

        # No balance row should exist for withdraw
        row = db.execute("SELECT amount_i64 FROM balances WHERE miner_id=?", (source,)).fetchone()
        assert row is None

        # But lock is still released
        lock = db.execute("SELECT status FROM lock_ledger WHERE bridge_transfer_id=80").fetchone()
        assert lock["status"] == "released"
