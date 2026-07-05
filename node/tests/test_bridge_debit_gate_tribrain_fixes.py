# SPDX-License-Identifier: MIT
"""Regression tests for the tribrain-flagged debit-gate fixes (2026-07-03).

Three defects found by adversarial review before landing the debit-on-lock stack:

  1. deposit-create was a raw-balance debit gate that ignored encumbered funds,
     so a deposit could drain balance a pending_ledger transfer was counting on
     (a double-spend). It must subtract encumbered_i64 before hard-debiting.
  2. the debit-on-lock migration debited balances and flipped source_debited as
     two unguarded statements; a re-run/partial-apply could double-debit.
  3. completion read source_debited from a snapshot taken before its BEGIN
     IMMEDIATE, so a concurrent settle could make it double-debit; it must
     re-read the flag under the write lock.
"""
import sqlite3
import sys

sys.path.insert(0, "node")

import bridge_api as ba
from bridge_api import BridgeTransferRequest


def _db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ba.init_bridge_schema(conn.cursor())
    conn.execute(
        "CREATE TABLE IF NOT EXISTS balances "
        "(miner_id TEXT PRIMARY KEY, amount_i64 INTEGER NOT NULL DEFAULT 0)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS lock_ledger ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, bridge_transfer_id INTEGER, "
        "miner_id TEXT NOT NULL, amount_i64 INTEGER NOT NULL, lock_type TEXT NOT NULL, "
        "locked_at INTEGER NOT NULL, unlock_at INTEGER NOT NULL, unlocked_at INTEGER, "
        "released_by TEXT, release_tx_hash TEXT, status TEXT NOT NULL DEFAULT 'locked', "
        "created_at INTEGER NOT NULL)"
    )
    conn.commit()
    return conn


SRC = "RTC" + "a" * 30
UNIT = 1_000_000


def _fund(conn, wallet, rtc):
    conn.execute(
        "INSERT OR REPLACE INTO balances (miner_id, amount_i64) VALUES (?, ?)",
        (wallet, int(rtc * UNIT)),
    )
    conn.commit()


def _bal(conn, wallet):
    row = conn.execute(
        "SELECT amount_i64 FROM balances WHERE miner_id = ?", (wallet,)
    ).fetchone()
    return row[0] if row else 0


def _deposit(amount_rtc):
    return BridgeTransferRequest(
        direction="deposit", source_chain="rustchain", dest_chain="base",
        source_address=SRC, dest_address="0x" + "b" * 40, amount_rtc=amount_rtc,
        memo="t", bridge_type="bottube",
    )


# ── Fix 1: deposit-create respects encumbrance ────────────────────────────

def test_deposit_create_rejects_when_pending_ledger_reserves_funds():
    """The exact double-spend the review found: 100 balance, 90 reserved by a
    pending transfer, a 100 deposit must NOT succeed on raw balance."""
    conn = _db()
    _fund(conn, SRC, 100)
    conn.execute(
        "CREATE TABLE pending_ledger (from_miner TEXT, amount_i64 INTEGER, status TEXT)"
    )
    conn.execute(
        "INSERT INTO pending_ledger (from_miner, amount_i64, status) VALUES (?, ?, 'pending')",
        (SRC, 90 * UNIT),
    )
    conn.commit()

    ok, result = ba.create_bridge_transfer(conn, _deposit(100))
    assert ok is False, result
    assert "available" in str(result).lower()
    # Balance untouched — the reserved 90 is still fully backed.
    assert _bal(conn, SRC) == 100 * UNIT


def test_deposit_create_allows_up_to_available_after_encumbrance():
    conn = _db()
    _fund(conn, SRC, 100)
    conn.execute(
        "CREATE TABLE pending_ledger (from_miner TEXT, amount_i64 INTEGER, status TEXT)"
    )
    conn.execute(
        "INSERT INTO pending_ledger (from_miner, amount_i64, status) VALUES (?, ?, 'pending')",
        (SRC, 90 * UNIT),
    )
    conn.commit()

    ok, _ = ba.create_bridge_transfer(conn, _deposit(10))   # 10 <= 100-90
    assert ok is True
    # Deposit hard-debited: 100 - 10 = 90 left, exactly covering the reservation.
    assert _bal(conn, SRC) == 90 * UNIT


def test_two_deposits_cannot_exceed_available_together():
    """Second deposit is itself encumbered by the first (undebited? no — first is
    debited at create; the guard is that raw balance already dropped)."""
    conn = _db()
    _fund(conn, SRC, 50)
    ok1, _ = ba.create_bridge_transfer(conn, _deposit(30))
    assert ok1 is True and _bal(conn, SRC) == 20 * UNIT
    ok2, _ = ba.create_bridge_transfer(conn, _deposit(30))   # only 20 left
    assert ok2 is False
    assert _bal(conn, SRC) == 20 * UNIT


# ── Fix 2: migration idempotent + guarded ─────────────────────────────────

def _insert_legacy_deposit(conn, amount_rtc, status="locked"):
    conn.execute(
        "INSERT INTO bridge_transfers (direction, source_chain, dest_chain, "
        "source_address, dest_address, amount_i64, amount_rtc, bridge_type, "
        "bridge_fee_i64, status, lock_epoch, created_at, updated_at, expires_at, "
        "tx_hash, memo, source_debited) VALUES "
        "('deposit','rustchain','base',?,?,?,?, 'bottube',0,?,0,0,0,0,?, 't', 0)",
        (SRC, "0x" + "b" * 40, int(amount_rtc * UNIT), amount_rtc, status,
         "hash-%s" % amount_rtc),
    )
    conn.commit()


def test_migration_debits_once_and_is_idempotent_on_rerun():
    conn = _db()
    _fund(conn, SRC, 100)
    _insert_legacy_deposit(conn, 30)

    ba.migrate_deposits_to_hard_locks(conn.cursor())
    conn.commit()
    assert _bal(conn, SRC) == 70 * UNIT
    flag = conn.execute(
        "SELECT source_debited FROM bridge_transfers WHERE source_address = ?", (SRC,)
    ).fetchone()[0]
    assert flag == 1

    # Re-run must be a no-op (row now source_debited=1, excluded by SELECT).
    ba.migrate_deposits_to_hard_locks(conn.cursor())
    conn.commit()
    assert _bal(conn, SRC) == 70 * UNIT


def test_migration_leaves_underfunded_row_unflagged_without_minting_negative():
    conn = _db()
    _fund(conn, SRC, 10)          # cannot cover a 30 deposit
    _insert_legacy_deposit(conn, 30)

    ba.migrate_deposits_to_hard_locks(conn.cursor())
    conn.commit()
    assert _bal(conn, SRC) == 10 * UNIT   # untouched, no negative
    flag = conn.execute(
        "SELECT source_debited FROM bridge_transfers WHERE source_address = ?", (SRC,)
    ).fetchone()[0]
    assert flag == 0                      # left for manual review


# ── Fix 3: completion honours the current DB source_debited ───────────────

def test_completion_of_hard_debited_deposit_does_not_debit_again():
    """A deposit hard-debited at create (source_debited=1) must not be debited a
    second time at completion."""
    conn = _db()
    _fund(conn, SRC, 100)
    ok, created = ba.create_bridge_transfer(conn, _deposit(40))
    assert ok is True
    assert _bal(conn, SRC) == 60 * UNIT
    tx = created["tx_hash"]

    ok2, _ = ba.update_external_confirmation(conn, tx, "0xext", confirmations=99)
    assert ok2 is True
    # No second debit: balance stays at 60.
    assert _bal(conn, SRC) == 60 * UNIT


def test_completion_settles_legacy_undebited_deposit_exactly_once():
    conn = _db()
    _fund(conn, SRC, 100)
    _insert_legacy_deposit(conn, 25, status="confirming")
    tx = conn.execute(
        "SELECT tx_hash FROM bridge_transfers WHERE source_address = ?", (SRC,)
    ).fetchone()[0]

    ok, _ = ba.update_external_confirmation(conn, tx, "0xext", confirmations=99)
    assert ok is True
    assert _bal(conn, SRC) == 75 * UNIT   # debited exactly once
    flag = conn.execute(
        "SELECT source_debited FROM bridge_transfers WHERE tx_hash = ?", (tx,)
    ).fetchone()[0]
    assert flag == 1
