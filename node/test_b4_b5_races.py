# SPDX-License-Identifier: MIT
"""
B4/B5 regression tests: TOCTOU race guards in release_lock/forfeit_lock.

B4: release_lock() UPDATE ... WHERE status='locked' prevents concurrent
    double-credit. Proved by idempotent test.
B5: forfeit_lock() same pattern.

NOTE: create_lock DEDUCTS from balance. release_lock CREDITS back.
Net: release returns balance to pre-lock level (not +lock_amount).
"""

import sys, os, sqlite3, time
sys.path.insert(0, os.path.dirname(__file__))
from lock_ledger import release_lock, forfeit_lock, create_lock, \
    LOCK_UNIT, init_lock_ledger_schema

DB = "/tmp/test_b4_b5.db"
U = LOCK_UNIT


def setup():
    if os.path.exists(DB):
        os.remove(DB)
    conn = sqlite3.connect(DB)
    init_lock_ledger_schema(conn.cursor())
    conn.execute("CREATE TABLE IF NOT EXISTS balances "
                 "(miner_id TEXT PRIMARY KEY, amount_i64 INTEGER DEFAULT 0)")
    conn.execute("INSERT OR IGNORE INTO balances (miner_id, amount_i64) "
                 "VALUES ('miner1', ?)", (1000 * U,))
    conn.commit()
    return conn


def teardown(conn):
    conn.close()
    if os.path.exists(DB):
        os.remove(DB)


def test_b4_release_lock_idempotent():
    """B4: Two release_lock() calls — second must fail with rowcount=0."""
    conn = setup()
    try:
        # Create a lock
        ok, data = create_lock(conn, "miner1", 100 * U, "bridge_deposit", unlock_at=int(time.time()) + 1)
        assert ok, f"create_lock failed: {data}"
        lock_id = data["lock_id"]

        # First release should succeed (admin bypass time check)
        ok, data = release_lock(conn, lock_id, released_by="admin")
        assert ok, f"First release should succeed: {data}"

        # Second release must fail
        ok, data = release_lock(conn, lock_id, released_by="admin")
        assert not ok, "Second release should fail (already released)"
        assert "already" in data.get("error", "").lower() or \
               "already" in data.get("hint", "").lower(), \
            f"Error should mention 'already': {data}"
    finally:
        teardown(conn)


def test_b4_release_double_credit_guard():
    """B4: After release, the miner balance is not double-credited."""
    conn = setup()
    try:
        # Snapshot balance
        before = conn.execute(
            "SELECT amount_i64 FROM balances WHERE miner_id='miner1'"
        ).fetchone()[0]

        ok, data = create_lock(conn, "miner1", 100 * U, "bridge_deposit", unlock_at=int(time.time()) + 1)
        assert ok
        lock_id = data["lock_id"]

        # Release twice — second fails
        ok1, _ = release_lock(conn, lock_id, released_by="admin")
        ok2, _ = release_lock(conn, lock_id, released_by="admin")
        assert ok1 and not ok2

        after = conn.execute(
            "SELECT amount_i64 FROM balances WHERE miner_id='miner1'"
        ).fetchone()[0]

        # Net: create_lock deducts 100U, release_lock credits 100U
        # Second release should NOT credit again
        assert after == before, \
            f"Balance should be {before}, got {after}"
    finally:
        teardown(conn)


def test_b5_forfeit_lock_idempotent():
    """B5: Two forfeit_lock() calls — second must fail."""
    conn = setup()
    try:
        ok, data = create_lock(conn, "miner1", 100 * U, "bridge_deposit", unlock_at=int(time.time()) + 1)
        assert ok
        lock_id = data["lock_id"]

        # First forfeit succeeds (no balance credit — treasury retains)
        ok, data = forfeit_lock(conn, lock_id, "test_slashing")
        assert ok, f"First forfeit should succeed: {data}"

        # Second forfeit fails (already forfeited)
        ok, data = forfeit_lock(conn, lock_id, "test_slashing")
        assert not ok, "Second forfeit should fail"
        assert "already" in data.get("error", "").lower() or \
               "already" in data.get("hint", "").lower()
    finally:
        teardown(conn)


def test_b5_forfeit_then_release_fails():
    """B5: After forfeit, release_lock() also fails."""
    conn = setup()
    try:
        ok, data = create_lock(conn, "miner1", 100 * U, "bridge_deposit", unlock_at=int(time.time()) + 1)
        assert ok
        lock_id = data["lock_id"]

        ok, _ = forfeit_lock(conn, lock_id, "slashing")
        assert ok

        # Release after forfeit must fail
        ok, data = release_lock(conn, lock_id, released_by="admin")
        assert not ok
    finally:
        teardown(conn)


def test_b4_b5_concurrent_simulation():
    """Simulate concurrent access via sequential idempotent check.
    True multi-thread requires shared DB + threading; this proves
    the SQL-level guard works by verifying rowcount=0 behaviour."""
    conn = setup()
    try:
        ok, data = create_lock(conn, "miner1", 50 * U, "bridge_deposit", unlock_at=int(time.time()) + 1)
        assert ok
        lock_id = data["lock_id"]

        # Call release_lock twice (simulating two concurrent callers)
        results = [
            release_lock(conn, lock_id, released_by="admin"),
            release_lock(conn, lock_id, released_by="admin"),
        ]
        successes = sum(1 for ok, _ in results if ok)
        assert successes == 1, \
            f"Exactly 1 release should succeed, got {successes}"
    finally:
        teardown(conn)


if __name__ == "__main__":
    test_b4_release_lock_idempotent()
    print("✓ test_b4_release_lock_idempotent")
    test_b4_release_double_credit_guard()
    print("✓ test_b4_release_double_credit_guard")
    test_b5_forfeit_lock_idempotent()
    print("✓ test_b5_forfeit_lock_idempotent")
    test_b5_forfeit_then_release_fails()
    print("✓ test_b5_forfeit_then_release_fails")
    test_b4_b5_concurrent_simulation()
    print("✓ test_b4_b5_concurrent_simulation")
    print("\n✅ ALL B4/B5 TESTS PASSED")
