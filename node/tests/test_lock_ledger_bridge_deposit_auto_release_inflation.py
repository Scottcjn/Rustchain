# SPDX-License-Identifier: MIT
"""Regression: the unattended lock auto-release worker must never refund a
bridge-managed (hard-debited, in-flight) deposit lock.

A bridge deposit hard-debits the source at create (debit-on-lock) and records a
`lock_ledger` row tied to the `bridge_transfers` row. Those funds are committed
to the external transfer; the bridge resolves them explicitly (void = atomic
refund + transfer void; completion = release WITHOUT refund).

Before the fix, `auto_release_expired_locks()` refunded ANY expired lock —
including the bridge deposit lock — via `release_lock()`, crediting the owner
back. That refund is not paired with a transfer void, so a later external
confirmation still completes the deposit cross-chain and the owner keeps BOTH
copies: 10 RTC created from nothing (supply inflation / double-spend).
"""
import sqlite3
import sys
import time
from pathlib import Path

NODE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(NODE))

import bridge_api  # noqa: E402
import lock_ledger  # noqa: E402

MINER = "RTC0123456789abcdef0123456789abcdef01234567"
UNIT = 1_000_000


def _make_db(tmp_path):
    db_path = str(tmp_path / "bridge_lock.db")
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("CREATE TABLE balances (miner_id TEXT PRIMARY KEY, amount_i64 INTEGER DEFAULT 0)")
    c.execute(
        """CREATE TABLE bridge_transfers (
            id INTEGER PRIMARY KEY AUTOINCREMENT, direction TEXT, source_chain TEXT,
            dest_chain TEXT, source_address TEXT, dest_address TEXT, amount_i64 INTEGER,
            amount_rtc REAL, bridge_type TEXT DEFAULT 'bottube', bridge_fee_i64 INTEGER DEFAULT 0,
            external_tx_hash TEXT, external_confirmations INTEGER DEFAULT 0,
            required_confirmations INTEGER DEFAULT 12, status TEXT DEFAULT 'pending',
            lock_epoch INTEGER, created_at INTEGER, updated_at INTEGER, expires_at INTEGER,
            completed_at INTEGER, tx_hash TEXT UNIQUE, voided_by TEXT, voided_reason TEXT,
            failure_reason TEXT, memo TEXT, source_debited INTEGER DEFAULT 0)"""
    )
    c.execute(
        """CREATE TABLE lock_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT, bridge_transfer_id INTEGER, miner_id TEXT,
            amount_i64 INTEGER, lock_type TEXT, locked_at INTEGER, unlock_at INTEGER,
            unlocked_at INTEGER, status TEXT DEFAULT 'locked', created_at INTEGER,
            released_by TEXT, release_tx_hash TEXT)"""
    )
    c.execute("INSERT INTO balances VALUES (?, ?)", (MINER, 100 * UNIT))
    conn.commit()
    return conn


def _balance(conn):
    return conn.execute(
        "SELECT amount_i64 FROM balances WHERE miner_id = ?", (MINER,)
    ).fetchone()[0]


def test_auto_release_does_not_refund_inflight_bridge_deposit(tmp_path):
    conn = _make_db(tmp_path)

    # 1. Miner initiates a 10 RTC bridge deposit -> hard-debited at create.
    req = bridge_api.BridgeTransferRequest(
        direction="deposit", source_chain="rustchain", dest_chain="solana",
        source_address=MINER, dest_address="4TRwNqXqXqXqXqXqXqXqXqXqXqXqXqXqXq",
        amount_rtc=10.0,
    )
    ok, res = bridge_api.create_bridge_transfer(conn, req)
    assert ok is True
    tx_hash = res["tx_hash"]
    assert _balance(conn) == 90 * UNIT  # funds committed to the cross-chain transfer

    # 2. The deposit lock's timer expires while confirmation is still pending.
    conn.execute(
        "UPDATE lock_ledger SET unlock_at = ? "
        "WHERE bridge_transfer_id = (SELECT id FROM bridge_transfers WHERE tx_hash = ?)",
        (int(time.time()) - 10, tx_hash),
    )
    conn.commit()

    # 3. The unattended periodic worker runs.
    lock_ledger.auto_release_expired_locks(conn)

    # It MUST NOT have refunded the in-flight deposit.
    assert _balance(conn) == 90 * UNIT, (
        "auto-release refunded a hard-debited in-flight bridge deposit"
    )

    # 4. External confirmation still completes the deposit (funds move cross-chain).
    ok, res = bridge_api.update_external_confirmation(
        conn, tx_hash, external_tx_hash="ext123", confirmations=12
    )
    assert ok is True and res["status"] == "completed"

    # Final invariant: the 10 RTC left the chain exactly once. No inflation.
    assert _balance(conn) == 90 * UNIT
    conn.close()


def test_auto_release_still_refunds_standalone_non_bridge_lock(tmp_path):
    """Guard against over-reach: a plain lock NOT tied to a bridge transfer
    (debited by create_lock, so a symmetric refund is correct) is still
    auto-released."""
    conn = _make_db(tmp_path)
    ok, res = lock_ledger.create_lock(
        conn, miner_id=MINER, amount_i64=10 * UNIT,
        lock_type="admin_hold", unlock_at=int(time.time()) + 1,
    )
    assert ok is True
    assert _balance(conn) == 90 * UNIT  # create_lock debited

    conn.execute("UPDATE lock_ledger SET unlock_at = ? WHERE id = ?",
                 (int(time.time()) - 10, res["lock_id"]))
    conn.commit()

    out = lock_ledger.auto_release_expired_locks(conn)
    assert out["released_count"] == 1
    assert _balance(conn) == 100 * UNIT  # symmetric refund restored
    conn.close()
