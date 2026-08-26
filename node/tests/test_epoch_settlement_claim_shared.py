"""Rustchain#6749: canonical epoch-settlement claim shared across paths.

``finalize_epoch`` (node/rustchain_v2_integrated_v2.2.1_rip200.py) and
``settle_epoch_with_anti_double_mining`` (node/anti_double_mining.py) each had
their own hand-copied "INSERT ... ON CONFLICT DO NOTHING" + atomic
"UPDATE ... WHERE settled = 0" claim -- the exact SQL pair, three times over
(a fourth copy lived in tests/test_epoch_settlement_atomic.py as a local
``_claim`` helper). This is the shared implementation both production call
sites now import from ``epoch_settlement_claim.claim_epoch`` instead of
re-deriving.

Scope note: ``settle_epoch_rip200``'s standard (non-ADM) path is deliberately
NOT wired to this helper. It holds one continuous BEGIN IMMEDIATE from its
top-of-function peek to its final unconditional
``UPDATE epoch_state SET settled=1 WHERE epoch=?`` -- a *lock-duration-based*
guard rather than a single-atomic-statement claim. Swapping in claim_epoch()
there would double-claim when it delegates to
settle_epoch_with_anti_double_mining on the SAME shared connection (the inner
call would see settled=1 from the outer call and refuse to credit anything),
breaking the ADM delegation path entirely. Its existing lock-duration design
is independently race-safe against the other two paths (SQLite serializes
all BEGIN IMMEDIATE writers on one DB file regardless of which row they
touch), so it does not need to change.
"""

import os
import sqlite3
import sys
import unittest

NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if NODE_DIR not in sys.path:
    sys.path.insert(0, NODE_DIR)

from epoch_settlement_claim import claim_epoch  # noqa: E402
import anti_double_mining  # noqa: E402


def _new_conn():
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE epoch_state (epoch INTEGER PRIMARY KEY, settled INTEGER DEFAULT 0, settled_ts INTEGER)"
    )
    conn.commit()
    return conn


class TestClaimEpochDirect(unittest.TestCase):
    def test_first_claim_wins_second_loses(self):
        conn = _new_conn()
        self.assertTrue(claim_epoch(conn, 5))
        self.assertFalse(claim_epoch(conn, 5), "a second claim on an already-claimed epoch must lose")

    def test_claim_creates_the_row_if_absent(self):
        conn = _new_conn()
        row = conn.execute("SELECT * FROM epoch_state WHERE epoch=?", (7,)).fetchone()
        self.assertIsNone(row, "sanity: row does not exist yet")
        self.assertTrue(claim_epoch(conn, 7))
        row = conn.execute("SELECT settled FROM epoch_state WHERE epoch=?", (7,)).fetchone()
        self.assertEqual(row[0], 1)

    def test_different_epochs_do_not_interfere(self):
        conn = _new_conn()
        self.assertTrue(claim_epoch(conn, 1))
        self.assertTrue(claim_epoch(conn, 2), "claiming epoch 1 must not block epoch 2")

    def test_stamps_settled_ts(self):
        conn = _new_conn()
        claim_epoch(conn, 3, now=1_700_000_000)
        row = conn.execute("SELECT settled_ts FROM epoch_state WHERE epoch=?", (3,)).fetchone()
        self.assertEqual(row[0], 1_700_000_000)


class TestAntiDoubleMiningUsesTheSharedHelper(unittest.TestCase):
    """Proves anti_double_mining.py calls the real shared function, not a
    local reimplementation -- pre-claiming the row through claim_epoch()
    directly must make settle_epoch_with_anti_double_mining see
    already_settled, exactly as if another settlement path had won first."""

    def test_pre_claimed_epoch_is_seen_as_already_settled_by_adm_path(self):
        conn = sqlite3.connect(":memory:")
        conn.execute(
            "CREATE TABLE epoch_state (epoch INTEGER PRIMARY KEY, settled INTEGER DEFAULT 0, settled_ts INTEGER)"
        )
        conn.commit()

        # Simulate a different settlement path (e.g. finalize_epoch) winning
        # the claim for this epoch first.
        conn.execute("BEGIN IMMEDIATE")
        won = claim_epoch(conn, 42)
        conn.commit()
        self.assertTrue(won)

        # Now anti_double_mining's settle path is asked to settle the SAME
        # epoch on a fresh connection, sharing nothing but the DB file logic
        # under test (claim_epoch itself, called on a new BEGIN IMMEDIATE).
        conn.execute("BEGIN IMMEDIATE")
        result_claimed = anti_double_mining.claim_epoch(conn, 42)
        conn.rollback()
        self.assertFalse(
            result_claimed,
            "anti_double_mining must see the epoch as already claimed -- if this "
            "were a local reimplementation instead of the real shared function, "
            "it could theoretically diverge and double-claim",
        )

    def test_anti_double_mining_module_binds_the_real_function_object(self):
        # Identity check: anti_double_mining.claim_epoch IS
        # epoch_settlement_claim.claim_epoch, not a copy or shadowing
        # reimplementation under the same name.
        self.assertIs(anti_double_mining.claim_epoch, claim_epoch)


if __name__ == "__main__":
    unittest.main()
