"""Regression: ADM must not leave `settled=1` committed when it pays nothing.

`settle_epoch_with_anti_double_mining` claims settlement (`UPDATE epoch_state SET
settled = 1`) BEFORE it knows whether any miner is eligible. Its `no_eligible_miners`
exit undoes that claim only `if own_conn` — but the live caller
(`rewards_implementation_rip200.settle_epoch_rip200`) always passes `existing_conn=db`
and then commits unconditionally, so the flag is durably committed while zero rewards
are written. The epoch's whole PER_EPOCH_URTC is never distributed and every retry is
answered `already_settled`.

The standard (non-ADM) path in the same caller does an ungated `db.rollback()` before
returning `no_eligible_miners`, which is the intended behaviour these tests pin.
"""
import os
import sqlite3
import sys
import tempfile
import unittest

NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if NODE_DIR not in sys.path:
    sys.path.insert(0, NODE_DIR)

import rewards_implementation_rip200 as rmod


def _db_with_only_ineligible_miner(epoch=1):
    """Enrolled miner whose attestation failed -> zero weight -> rewards == {}."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    c = sqlite3.connect(path)
    c.execute("CREATE TABLE epoch_state (epoch INTEGER PRIMARY KEY, settled INTEGER DEFAULT 0, settled_ts INTEGER)")
    c.execute("CREATE TABLE epoch_enroll (epoch INTEGER, miner_pk TEXT, weight INTEGER DEFAULT 100)")
    c.execute("CREATE TABLE miner_attest_recent (miner TEXT PRIMARY KEY, device_arch TEXT, ts_ok INTEGER, "
              "fingerprint_passed INTEGER DEFAULT 1, entropy_score REAL, fingerprint_checks_json TEXT)")
    c.execute("CREATE TABLE balances (miner_id TEXT PRIMARY KEY, amount_i64 INTEGER DEFAULT 0)")
    c.execute("CREATE TABLE ledger (id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER, epoch INTEGER, "
              "miner_id TEXT, delta_i64 INTEGER, reason TEXT)")
    c.execute("CREATE TABLE epoch_rewards (epoch INTEGER, miner_id TEXT, share_i64 INTEGER)")
    # Created by the live node (rustchain_v2_integrated:3246); ADM joins against it.
    c.execute("CREATE TABLE miner_fingerprint_history (id INTEGER PRIMARY KEY AUTOINCREMENT, "
              "miner TEXT NOT NULL, ts INTEGER NOT NULL, profile_json TEXT NOT NULL)")
    # The live node pre-creates the epoch_state row (settled=0) before settling.
    c.execute("INSERT INTO epoch_state (epoch, settled) VALUES (?, 0)", (epoch,))
    c.execute("INSERT INTO epoch_enroll (epoch, miner_pk, weight) VALUES (?, ?, ?)", (epoch, "MINER_A", 100))
    # fingerprint_passed = 0 -> no positive-weight miners -> empty reward map.
    c.execute("INSERT INTO miner_attest_recent (miner, device_arch, ts_ok, fingerprint_passed, entropy_score) "
              "VALUES (?, ?, ?, 0, 0.0)", ("MINER_A", "x86_64", 0))
    c.commit()
    c.close()
    return path


def _settled(path, epoch):
    with sqlite3.connect(path) as c:
        row = c.execute("SELECT settled FROM epoch_state WHERE epoch=?", (epoch,)).fetchone()
    return bool(row and row[0] == 1)


def _paid_rows(path, epoch):
    with sqlite3.connect(path) as c:
        rewards = c.execute("SELECT COUNT(*) FROM epoch_rewards WHERE epoch=?", (epoch,)).fetchone()[0]
        balances = c.execute("SELECT COUNT(*) FROM balances").fetchone()[0]
    return rewards, balances


@unittest.skipUnless(rmod.ANTI_DOUBLE_MINING_AVAILABLE, "anti_double_mining module unavailable")
class AdmNoEligibleMinersMustNotBurnEpochTest(unittest.TestCase):
    """Exercises the REAL ADM function on the shared-connection (live) path."""

    def setUp(self):
        self.epoch = 1
        self.path = _db_with_only_ineligible_miner(self.epoch)
        self.addCleanup(lambda: os.path.exists(self.path) and os.unlink(self.path))

    def test_failed_settlement_leaves_epoch_unsettled(self):
        result = rmod.settle_epoch_rip200(self.path, epoch=self.epoch, enable_anti_double_mining=True)

        self.assertFalse(result.get("ok"), f"expected failure, got {result}")
        self.assertEqual(result.get("error"), "no_eligible_miners")
        self.assertEqual(_paid_rows(self.path, self.epoch), (0, 0), "nothing should have been paid")
        # The claim must be undone: a settlement that paid nothing is not a settlement.
        self.assertFalse(
            _settled(self.path, self.epoch),
            "epoch was committed as settled=1 while paying zero rewards — "
            "its emission is burned and retry is impossible",
        )

    def test_epoch_can_be_retried_after_failure(self):
        rmod.settle_epoch_rip200(self.path, epoch=self.epoch, enable_anti_double_mining=True)

        # Operator fixes the fleet: the miner now passes attestation.
        with sqlite3.connect(self.path) as c:
            c.execute("UPDATE miner_attest_recent SET fingerprint_passed = 1, entropy_score = 1.0 "
                      "WHERE miner = ?", ("MINER_A",))
            c.commit()

        retry = rmod.settle_epoch_rip200(self.path, epoch=self.epoch, enable_anti_double_mining=True)

        self.assertNotEqual(
            retry.get("already_settled"), True,
            "retry was refused with already_settled — the failed attempt burned the epoch",
        )
        rewards_rows, _ = _paid_rows(self.path, self.epoch)
        self.assertGreater(rewards_rows, 0, "retry should have distributed the epoch's rewards")


if __name__ == "__main__":
    unittest.main()
