"""
Regression tests: lock_ledger must not credit balances for bridge-owned locks.

bridge_api.create_bridge_transfer() hard-debits the source, writes the
lock_ledger row directly (it never calls lock_ledger.create_lock()), and tracks
the refund itself on bridge_transfers.source_debited. lock_ledger.release_lock()
credits unconditionally because it is the counterpart of create_lock(), which
debits — but that pairing does not hold for bridge-produced rows, so releasing
one reverses a debit the bridge still considers outstanding.

Every test here fails on main:
  - admin release of a pending deposit un-does the hard debit
  - the routine auto-release worker does the same once the lock expires
  - release followed by the bridge's own void refunds twice (100 -> 200 RTC)
"""

import os
import sqlite3
import sys
import time

import pytest

NODE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "node")
if NODE_DIR not in sys.path:
    sys.path.insert(0, NODE_DIR)

import bridge_api  # noqa: E402
import lock_ledger  # noqa: E402

UNIT = bridge_api.BRIDGE_UNIT


@pytest.fixture
def conn(tmp_path):
    db = sqlite3.connect(str(tmp_path / "bridge.db"))
    cur = db.cursor()
    cur.execute(
        "CREATE TABLE IF NOT EXISTS balances ("
        "  miner_id TEXT PRIMARY KEY,"
        "  amount_i64 INTEGER NOT NULL DEFAULT 0"
        ")"
    )
    bridge_api.init_bridge_schema(cur)
    lock_ledger.init_lock_ledger_schema(cur)
    cur.execute("INSERT INTO balances VALUES (?, ?)", ("alice", 100 * UNIT))
    db.commit()
    yield db
    db.close()


def _balance(db, miner_id="alice"):
    row = db.execute(
        "SELECT amount_i64 FROM balances WHERE miner_id = ?", (miner_id,)
    ).fetchone()
    return row[0] if row else 0


def _open_deposit(db, amount_rtc=100.0):
    """Open a real deposit: hard-debits alice and writes the bridge-owned lock."""
    request = bridge_api.BridgeTransferRequest(
        direction="deposit",
        source_chain="rustchain",
        dest_chain="solana",
        source_address="alice",
        dest_address="SoLaNaAddr",
        amount_rtc=amount_rtc,
        bridge_type="lock_mint",
        memo=None,
    )
    ok, _ = bridge_api.create_bridge_transfer(db, request)
    assert ok, "fixture: deposit should open"
    tx_hash, lock_id = db.execute(
        "SELECT t.tx_hash, l.id FROM bridge_transfers t"
        " JOIN lock_ledger l ON l.bridge_transfer_id = t.id"
    ).fetchone()
    assert _balance(db) == 0, "fixture: deposit hard-debits the source"
    return tx_hash, lock_id


def test_admin_release_does_not_credit_bridge_deposit(conn):
    """Admin release of a bridge lock must not undo the bridge's hard debit."""
    _tx_hash, lock_id = _open_deposit(conn)

    # released_by="admin" bypasses the unlock timer by design.
    ok, result = lock_ledger.release_lock(conn, lock_id, released_by="admin")

    assert not ok, "bridge-owned locks must not be released via lock_ledger"
    assert "bridge" in result["error"].lower()
    assert _balance(conn) == 0, "hard debit must stand while the deposit is pending"


def test_release_then_complete_does_not_mint(conn):
    """The deposit completes on Solana; alice must not also keep her RTC here."""
    tx_hash, lock_id = _open_deposit(conn)

    lock_ledger.release_lock(conn, lock_id, released_by="admin")
    ok, result = bridge_api.update_external_confirmation(conn, tx_hash, "solana_tx_abc", 12)
    assert ok and result["status"] == "completed"

    # She holds 100 RTC on Solana. Any RustChain balance here is minted supply.
    assert _balance(conn) == 0, "completed deposit must not leave a RustChain balance"


def test_release_then_void_refunds_once(conn):
    """Void refunds the source exactly once, not on top of a lock release."""
    tx_hash, lock_id = _open_deposit(conn)

    lock_ledger.release_lock(conn, lock_id, released_by="admin")
    ok, _ = bridge_api.void_bridge_transfer(conn, tx_hash, reason="stuck", voided_by="admin")
    assert ok

    assert _balance(conn) == 100 * UNIT, "void must refund exactly once (not 200 RTC)"


def test_auto_release_worker_skips_bridge_owned_locks(conn):
    """The routine worker must not credit an expired-but-pending deposit."""
    _tx_hash, _lock_id = _open_deposit(conn)

    # The 7-day lock expires while the deposit is still pending.
    conn.execute("UPDATE lock_ledger SET unlock_at = ?", (int(time.time()) - 1,))
    conn.commit()

    result = lock_ledger.auto_release_expired_locks(conn)

    assert result["released_count"] == 0
    assert result["skipped_bridge_owned"] == 1
    assert result["errors"] == [], "skipping is a normal state, not a per-run error"
    assert _balance(conn) == 0, "worker must not undo the bridge's hard debit"
    status, source_debited = conn.execute(
        "SELECT status, source_debited FROM bridge_transfers"
    ).fetchone()
    assert (status, source_debited) == ("pending", 1)


def test_standalone_lock_release_still_credits(conn):
    """Guard against over-reach: non-bridge locks keep debit/credit symmetry."""
    unlock_at = int(time.time()) + 3600
    ok, created = lock_ledger.create_lock(
        conn,
        miner_id="alice",
        amount_i64=40 * UNIT,
        lock_type="bridge_deposit",
        unlock_at=unlock_at,
    )
    assert ok, created
    assert _balance(conn) == 60 * UNIT, "create_lock debits"

    ok, _ = lock_ledger.release_lock(conn, created["lock_id"], released_by="admin")

    assert ok, "locks created here are still ours to release"
    assert _balance(conn) == 100 * UNIT, "release_lock credits its own locks back"
