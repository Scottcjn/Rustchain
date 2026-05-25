# SPDX-License-Identifier: MIT
"""
PoC: A6 — add_box() no PRIMARY KEY conflict handling

add_box() (line 237) does a plain INSERT INTO utxo_boxes with no
INSERT OR IGNORE / INSERT OR REPLACE / ON CONFLICT clause and no
try/except around conn.execute().  If a box_id already exists:

  - With external conn (batch mode): IntegrityError crashes entire batch
  - With own conn: IntegrityError on execute() propagates unhandled,
    connection close in finally only runs after the exception passes

This should use INSERT OR IGNORE (or catch IntegrityError for logging).
"""

import sys
import os
import sqlite3

sys.path.insert(0, os.path.dirname(__file__))
from utxo_db import UtxoDB, UNIT

DB_PATH = "/tmp/test_a6_conflict.db"


def _reset_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)


def _setup_db():
    _reset_db()
    db = UtxoDB(DB_PATH)
    db.init_tables()
    return db


def test_add_box_duplicate_own_conn_raises():
    """A6: add_box() with own conn raises unhandled IntegrityError on duplicate box_id"""
    db = _setup_db()

    box = dict(
        box_id="duplicate_box_001",
        value_nrtc=50 * UNIT,
        proposition="b0b",
        owner_address="alice",
        creation_height=100,
        transaction_id="tx_a",
        output_index=0,
    )

    # First insert works fine
    db.add_box(box)
    print("[OK] First add_box succeeded")

    # Second insert with same box_id — should raise IntegrityError
    try:
        db.add_box(box)
        print("[BUG] Duplicate add_box ACCEPTED — should have raised IntegrityError")
        return False
    except sqlite3.IntegrityError:
        print("[OK] Duplicate add_box raised IntegrityError as expected")
    except Exception as e:
        print("[INFO] Duplicate raised unexpected exception: %s: %s" % (type(e).__name__, e))

    # Verify only one box exists
    conn = sqlite3.connect(DB_PATH)
    count = conn.execute("SELECT COUNT(*) FROM utxo_boxes").fetchone()[0]
    conn.close()
    assert count == 1, "Expected 1 box, got %d" % count
    print("[OK] Exactly 1 box in DB (count=%d)" % count)

    return True


def test_add_box_batch_crash():
    """A6: duplicate add_box crashes entire batch via external conn"""
    db = _setup_db()
    conn = db._conn()
    try:
        conn.execute("BEGIN IMMEDIATE")

        # First box — works
        db.add_box(dict(
            box_id="batch_box_001", value_nrtc=10 * UNIT,
            proposition="a", owner_address="alice",
            creation_height=100, transaction_id="tx1", output_index=0,
        ), conn=conn)
        print("[OK] Batch first add_box succeeded")

        # Second box with SAME box_id — should gracefully handle, NOT crash batch
        try:
            db.add_box(dict(
                box_id="batch_box_001", value_nrtc=20 * UNIT,
                proposition="b", owner_address="bob",
                creation_height=100, transaction_id="tx1", output_index=1,
            ), conn=conn)
            print("[BUG] Duplicate in batch ACCEPTED — data integrity lost")
            conn.rollback()
            return False
        except sqlite3.IntegrityError:
            print("[OK] Duplicate in batch raised IntegrityError")
            # The batch transaction is now doomed — any further ops in this
            # transaction will fail with "cannot commit - no transaction is active"
            # due to SQLite's automatic rollback on constraint violation.

        conn.rollback()
        print("[OK] Batch rolled back cleanly")
    finally:
        conn.close()

    return True


def test_add_box_duplicate_cleanup_no_connection_leak():
    """Verify own_conn mode doesn't leak connections on IntegrityError"""
    db = _setup_db()

    box = dict(
        box_id="leak_test_001",
        value_nrtc=50 * UNIT,
        proposition="a", owner_address="carol",
        creation_height=100, transaction_id="tx_l", output_index=0,
    )

    # First insert
    db.add_box(box)

    # Second insert — should not crash and should close its own conn
    try:
        db.add_box(box)
        print("[BUG] No error on duplicate (should at least warn)")
    except sqlite3.IntegrityError:
        print("[OK] IntegrityError raised and connection closed in finally")
    except Exception as e:
        print("[INFO] Unexpected: %s: %s" % (type(e).__name__, e))

    # Verify no leak — try another add with unique box_id
    box2 = dict(box_id="leak_test_002", value_nrtc=1 * UNIT,
                 proposition="a", owner_address="carol",
                 creation_height=100, transaction_id="tx_l2", output_index=1)
    try:
        db.add_box(box2)
        print("[OK] Second add_box succeeded — no connection leak")
    except Exception as e:
        print("[BUG] Connection leak: %s: %s" % (type(e).__name__, e))
        return False

    return True


if __name__ == "__main__":
    results = []
    for name, fn in [
        ("test_add_box_duplicate_own_conn_raises", test_add_box_duplicate_own_conn_raises),
        ("test_add_box_batch_crash", test_add_box_batch_crash),
        ("test_add_box_duplicate_cleanup_no_connection_leak", test_add_box_duplicate_cleanup_no_connection_leak),
    ]:
        try:
            ok = fn()
            results.append((name, "PASS" if ok else "FAIL"))
        except Exception as e:
            results.append((name, "EXCEPTION: %s" % e))

    print("\n=== RESULTS ===")
    for name, status in results:
        print("  %s\t%s" % (status, name))
    all_pass = all(s == "PASS" for _, s in results)
    print("\nOVERALL: %s" % ("ALL PASS" if all_pass else "SOME FAILED"))
    sys.exit(0 if all_pass else 1)
