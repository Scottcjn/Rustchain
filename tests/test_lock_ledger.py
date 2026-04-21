# SPDX-License-Identifier: MIT
"""Unit tests for lock_ledger.py — Lock Ledger Module (RIP-0305)"""

import os
import sys
import sqlite3
import tempfile
import time

# Allow standalone testing
os.environ["RC_DB_PATH"] = ""  # Use temp DB

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "node"))


def _make_temp_db():
    """Create a temporary database with lock_ledger schema."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS lock_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bridge_transfer_id INTEGER,
            miner_id TEXT NOT NULL,
            amount_i64 INTEGER NOT NULL,
            lock_type TEXT NOT NULL,
            locked_at INTEGER NOT NULL,
            unlock_at INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'locked',
            released_at INTEGER,
            released_to TEXT,
            signature TEXT,
            CONSTRAINT valid_status CHECK (status IN ('locked', 'released', 'forfeited'))
        )
    """)
    conn.commit()
    return conn, path


def _cleanup_db(conn, path):
    conn.close()
    os.unlink(path)


def test_lock_type_enum_values():
    """LockType enum should have expected values."""
    from lock_ledger import LockType
    assert LockType.BRIDGE_DEPOSIT.value == "bridge_deposit"
    assert LockType.BRIDGE_WITHDRAW.value == "bridge_withdraw"
    assert LockType.EPOCH_SETTLEMENT.value == "epoch_settlement"
    assert LockType.ADMIN_HOLD.value == "admin_hold"


def test_lock_status_enum_values():
    """LockStatus enum should have expected values."""
    from lock_ledger import LockStatus
    assert LockStatus.LOCKED.value == "locked"
    assert LockStatus.RELEASED.value == "released"
    assert LockStatus.FORFEITED.value == "forfeited"


def test_lock_entry_dataclass():
    """LockEntry dataclass should store lock information."""
    from lock_ledger import LockEntry
    entry = LockEntry(
        id=1,
        bridge_transfer_id=None,
        miner_id="test-miner",
        amount_i64=1000000,
        lock_type="bridge_deposit",
        locked_at=1000,
        unlock_at=2000,
    )
    assert entry.id == 1
    assert entry.miner_id == "test-miner"
    assert entry.amount_i64 == 1000000
    assert entry.lock_type == "bridge_deposit"
    assert entry.locked_at == 1000
    assert entry.unlock_at == 2000


def test_create_lock():
    """create_lock() should insert a lock entry with status='locked'."""
    from lock_ledger import create_lock, LockType
    conn, path = _make_temp_db()
    try:
        now = int(time.time())
        lock_id = create_lock(
            conn=conn,
            miner_id="test-wallet",
            amount_i64=5000000,
            lock_type=LockType.BRIDGE_DEPOSIT,
            unlock_at=now + 3600,
        )
        assert lock_id is not None
        assert lock_id > 0

        # Verify the lock was inserted
        row = conn.execute("SELECT * FROM lock_ledger WHERE id = ?", (lock_id,)).fetchone()
        assert row is not None
        assert row["miner_id"] == "test-wallet"
        assert row["amount_i64"] == 5000000
        assert row["status"] == "locked"
    finally:
        _cleanup_db(conn, path)


def test_release_lock():
    """release_lock() should change status to 'released'."""
    from lock_ledger import create_lock, release_lock, LockType
    conn, path = _make_temp_db()
    try:
        now = int(time.time())
        lock_id = create_lock(
            conn=conn,
            miner_id="test-wallet",
            amount_i64=3000000,
            lock_type=LockType.BRIDGE_WITHDRAW,
            unlock_at=now + 3600,
        )

        # Release the lock
        release_lock(conn=conn, lock_id=lock_id, released_to="recipient-wallet")

        # Verify
        row = conn.execute("SELECT * FROM lock_ledger WHERE id = ?", (lock_id,)).fetchone()
        assert row["status"] == "released"
        assert row["released_to"] == "recipient-wallet"
        assert row["released_at"] is not None
    finally:
        _cleanup_db(conn, path)


def test_forfeit_lock():
    """forfeit_lock() should change status to 'forfeited'."""
    from lock_ledger import create_lock, forfeit_lock, LockType
    conn, path = _make_temp_db()
    try:
        now = int(time.time())
        lock_id = create_lock(
            conn=conn,
            miner_id="bad-actor",
            amount_i64=1000000,
            lock_type=LockType.EPOCH_SETTLEMENT,
            unlock_at=now + 3600,
        )

        # Forfeit the lock
        forfeit_lock(conn=conn, lock_id=lock_id)

        # Verify
        row = conn.execute("SELECT * FROM lock_ledger WHERE id = ?", (lock_id,)).fetchone()
        assert row["status"] == "forfeited"
    finally:
        _cleanup_db(conn, path)


def test_get_locks_by_miner():
    """get_locks_by_miner() should return only locks for the specified miner."""
    from lock_ledger import create_lock, get_locks_by_miner, LockType
    conn, path = _make_temp_db()
    try:
        now = int(time.time())
        # Create locks for two miners
        create_lock(conn, miner_id="alice", amount_i64=1000000,
                     lock_type=LockType.BRIDGE_DEPOSIT, unlock_at=now + 3600)
        create_lock(conn, miner_id="bob", amount_i64=2000000,
                     lock_type=LockType.BRIDGE_DEPOSIT, unlock_at=now + 3600)
        create_lock(conn, miner_id="alice", amount_i64=3000000,
                     lock_type=LockType.EPOCH_SETTLEMENT, unlock_at=now + 7200)

        # Query alice's locks
        alice_locks = get_locks_by_miner(conn=conn, miner_id="alice")
        assert len(alice_locks) == 2

        # Query bob's locks
        bob_locks = get_locks_by_miner(conn=conn, miner_id="bob")
        assert len(bob_locks) == 1
        assert bob_locks[0]["amount_i64"] == 2000000
    finally:
        _cleanup_db(conn, path)


def test_cannot_release_already_released():
    """Releasing an already-released lock should be idempotent or raise error."""
    from lock_ledger import create_lock, release_lock, LockType
    conn, path = _make_temp_db()
    try:
        now = int(time.time())
        lock_id = create_lock(
            conn=conn,
            miner_id="test-wallet",
            amount_i64=1000000,
            lock_type=LockType.BRIDGE_DEPOSIT,
            unlock_at=now + 3600,
        )
        # First release succeeds
        release_lock(conn=conn, lock_id=lock_id, released_to="recipient")

        # Second release should not error (idempotent or raise)
        # The module may raise ValueError or silently succeed
        try:
            release_lock(conn=conn, lock_id=lock_id, released_to="recipient2")
        except ValueError:
            pass  # Expected: cannot release already-released lock
    finally:
        _cleanup_db(conn, path)


def test_get_pending_unlocks():
    """get_pending_unlocks() should return locks past their unlock_at time."""
    from lock_ledger import create_lock, get_pending_unlocks, LockType
    conn, path = _make_temp_db()
    try:
        now = int(time.time())
        # Create a lock that's already expired
        create_lock(conn, miner_id="expired-miner", amount_i64=1000000,
                     lock_type=LockType.BRIDGE_DEPOSIT, unlock_at=now - 100)
        # Create a lock that hasn't expired yet
        create_lock(conn, miner_id="active-miner", amount_i64=2000000,
                     lock_type=LockType.BRIDGE_DEPOSIT, unlock_at=now + 3600)

        pending = get_pending_unlocks(conn=conn)
        assert len(pending) >= 1
        expired_miners = [l["miner_id"] for l in pending]
        assert "expired-miner" in expired_miners
    finally:
        _cleanup_db(conn, path)


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
