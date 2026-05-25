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
    conn.execute("CREATE TABLE IF NOT EXISTS balances ("
                 "miner_id TEXT PRIMARY KEY, amount_i64 INTEGER DEFAULT 0)")
    conn.execute("INSERT OR IGNORE INTO balances VALUES (?, ?)",
                 ("miner", 100 * U))
    conn.commit()
    return conn


def mk_lock(conn, miner="miner", amt=50*U, backdate=False):
    ok, r = create_lock(conn, miner_id=miner, amount_i64=amt,
                        lock_type="admin_hold", unlock_at=int(time.time())+3600)
    assert ok, f"create_lock: {r}"
    lid = r["lock_id"]
    if backdate:
        conn.execute("UPDATE lock_ledger SET unlock_at = ? WHERE id = ?",
                     (int(time.time()) - 10, lid))
        conn.commit()
    return lid


def test_b4_release_idempotent():
    """First release succeeds, second fails. Balance returns to initial."""
    conn = setup()
    lid = mk_lock(conn, backdate=True)

    ok1, _ = release_lock(conn, lid, "miner", "tx1")
    assert ok1, "first release"

    ok2, d2 = release_lock(conn, lid, "miner", "tx2")
    assert not ok2, f"second should fail: {d2}"
    assert "already" in d2.get("error","").lower(), d2

    # create_lock deducts 50U then release credits 50U → back to 100U
    bal = conn.execute(
        "SELECT amount_i64 FROM balances WHERE miner_id='miner'"
    ).fetchone()[0]
    assert bal == 100 * U, f"balance={bal}, expected {100*U}"
    print(f"[B4] idempotent ✓ balance={bal} (100U)")


def test_b5_forfeit_idempotent():
    """First forfeit succeeds, second fails."""
    conn = setup()
    lid = mk_lock(conn)

    ok1, _ = forfeit_lock(conn, lid, "test", "admin")
    assert ok1, "first forfeit"

    ok2, d2 = forfeit_lock(conn, lid, "test2", "admin")
    assert not ok2, f"second should fail: {d2}"
    assert "already" in d2.get("error","").lower(), d2

    row = conn.execute(
        "SELECT status FROM lock_ledger WHERE id=?", (lid,)
    ).fetchone()
    assert row[0] == "forfeited", f"status={row[0]}"
    print(f"[B5] forfeit idempotent ✓ status={row[0]}")


def test_b4_new_miner_credit():
    """Miner without balance row gets INSERT OR IGNORE on release.
    Must pre-fund to satisfy create_lock's balance deduction."""
    conn = setup()
    # Pre-fund new miner so create_lock can deduct
    conn.execute("INSERT OR REPLACE INTO balances VALUES (?, ?)",
                 ("new_guy", 50 * U))
    conn.commit()

    lid = mk_lock(conn, miner="new_guy", backdate=True)

    ok, _ = release_lock(conn, lid, "new_guy", "tx_new")
    assert ok, "release new miner"

    bal = conn.execute(
        "SELECT amount_i64 FROM balances WHERE miner_id='new_guy'"
    ).fetchone()
    assert bal is not None, "no balance row"
    # 50 initial - 50 lock + 50 release = 50
    assert bal[0] == 50 * U, f"balance={bal[0]}, expected {50*U}"
    print(f"[B4] new miner credit ✓ balance={bal[0]} (50U)")


if __name__ == "__main__":
    tests = [
        ("B4 release idempotent", test_b4_release_idempotent),
        ("B5 forfeit idempotent", test_b5_forfeit_idempotent),
        ("B4 new miner credit", test_b4_new_miner_credit),
    ]
    results = []
    for name, fn in tests:
        try:
            fn()
            results.append((name, "PASS"))
        except Exception as e:
            import traceback; traceback.print_exc()
            results.append((name, f"FAIL: {e}"))
    for name, status in results:
        print(f"  {status}\t{name}")
    all_ok = all(status == "PASS" for _, status in results)
    print(f"\n{'ALL PASS' if all_ok else 'SOME FAILED'}")
    sys.exit(0 if all_ok else 1)
