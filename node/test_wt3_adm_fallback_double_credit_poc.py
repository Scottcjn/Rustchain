#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
PoC: ADM-failure fallback double-credit in settle_epoch_rip200().

Root cause (node/rewards_implementation_rip200.py):

  When anti-double-mining (ADM) is enabled but its settlement raises, the
  default (RC_REQUIRE_ADM unset) recovery path does:

      db.rollback()                 # line 212 — RELEASES the write lock
      ...
      db.execute("BEGIN IMMEDIATE") # line 221 — re-acquires the write lock
      # ... falls straight through to the standard crediting path ...

  The `already_settled` guard is checked only ONCE, at the top of the
  original transaction (line 162). It is NOT re-checked after the write
  lock is released and re-acquired in the fallback. A second settler that
  commits this epoch during that release window is therefore invisible to
  this caller, which then credits the SAME epoch a second time.

  The existing regression suite (test_rewards_settle_race.py) only covers
  the ADM *success* path and the plain standard path; the ADM
  *failure -> standard fallback* path has no re-check and is unguarded.

This test models the documented race deterministically by injecting a
concurrent, fully-committed settlement (on a separate connection) into the
exact rollback->BEGIN IMMEDIATE window, via a rollback hook. On unpatched
main the epoch is credited TWICE (m1: 200, m2: 400). With the fix (re-check
settled after the fallback BEGIN IMMEDIATE) the second credit is suppressed.
"""

import os
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _init_db(path):
    with sqlite3.connect(path) as db:
        db.executescript(
            """
            CREATE TABLE epoch_state (
                epoch INTEGER PRIMARY KEY,
                settled INTEGER DEFAULT 0,
                settled_ts INTEGER
            );
            CREATE TABLE balances (
                miner_id TEXT PRIMARY KEY,
                amount_i64 INTEGER NOT NULL
            );
            CREATE TABLE ledger (
                ts INTEGER, epoch INTEGER, miner_id TEXT,
                delta_i64 INTEGER, reason TEXT
            );
            CREATE TABLE epoch_rewards (
                epoch INTEGER, miner_id TEXT, share_i64 INTEGER
            );
            CREATE TABLE miner_attest_recent (
                miner TEXT, device_arch TEXT
            );
            """
        )
        db.executemany(
            "INSERT INTO miner_attest_recent (miner, device_arch) VALUES (?, ?)",
            [("m1", "x86_64"), ("m2", "x86_64")],
        )
        db.execute("INSERT INTO epoch_state(epoch, settled, settled_ts) VALUES (0, 0, 0)")
        db.commit()


REWARDS = {"m1": 100, "m2": 200}


def _concurrent_settle(db_path, epoch):
    """A *second* settler that fully commits this epoch on its own connection.

    Models a worker that wins the write lock during the fallback's
    rollback()->BEGIN IMMEDIATE release window.
    """
    other = sqlite3.connect(db_path, timeout=10)
    try:
        other.execute("BEGIN IMMEDIATE")
        for miner_id, share in REWARDS.items():
            other.execute(
                "INSERT INTO balances (miner_id, amount_i64) VALUES (?, ?) "
                "ON CONFLICT(miner_id) DO UPDATE SET amount_i64 = amount_i64 + ?",
                (miner_id, share, share),
            )
            other.execute(
                "INSERT INTO epoch_rewards (epoch, miner_id, share_i64) VALUES (?, ?, ?)",
                (epoch, miner_id, share),
            )
        other.execute(
            "INSERT OR REPLACE INTO epoch_state (epoch, settled, settled_ts) VALUES (?, 1, 0)",
            (epoch,),
        )
        other.commit()
    finally:
        other.close()


class TestAdmFallbackDoubleCredit(unittest.TestCase):
    def _load_module(self):
        try:
            import rewards_implementation_rip200 as rip200
        except ImportError:
            import node.rewards_implementation_rip200 as rip200
        return rip200

    def test_fallback_does_not_double_credit(self):
        rip200 = self._load_module()

        # Force the ADM branch to be taken, then fail, so we exercise the
        # default standard-rewards fallback.
        orig_adm_avail = rip200.ANTI_DOUBLE_MINING_AVAILABLE
        orig_adm_fn = getattr(rip200, "settle_epoch_with_anti_double_mining", None)
        orig_calc = rip200.calculate_epoch_rewards_time_aged
        orig_age = rip200.get_chain_age_years
        orig_mult = rip200.get_time_aged_multiplier

        rip200.ANTI_DOUBLE_MINING_AVAILABLE = True

        def failing_adm(*_a, **_k):
            raise RuntimeError("simulated ADM failure")

        rip200.settle_epoch_with_anti_double_mining = failing_adm
        rip200.calculate_epoch_rewards_time_aged = lambda *_a, **_k: dict(REWARDS)
        rip200.get_chain_age_years = lambda *_a, **_k: 1.0
        rip200.get_time_aged_multiplier = lambda *_a, **_k: 1.0

        try:
            with tempfile.TemporaryDirectory() as td:
                db_path = os.path.join(td, "test.db")
                _init_db(db_path)

                # Drive settlement on a connection we control so we can hook
                # rollback() and inject the concurrent settle into the exact
                # release window between rollback() and BEGIN IMMEDIATE.
                # sqlite3.Connection.rollback is read-only on instances, so we
                # subclass via the connection factory.
                _state = {"injected": False, "db_path": db_path}

                class HookedConn(sqlite3.Connection):
                    def rollback(self):
                        super().rollback()  # releases the write lock, like line 212
                        if not _state["injected"]:
                            _state["injected"] = True
                            # Concurrent worker settles + commits this epoch now,
                            # inside the release window.
                            _concurrent_settle(_state["db_path"], 0)

                conn = sqlite3.connect(db_path, timeout=10, factory=HookedConn)
                try:
                    result = rip200.settle_epoch_rip200(conn, epoch=0)
                finally:
                    conn.close()

                with sqlite3.connect(db_path) as db:
                    balances = dict(
                        db.execute(
                            "SELECT miner_id, amount_i64 FROM balances ORDER BY miner_id"
                        ).fetchall()
                    )
                    reward_rows = db.execute(
                        "SELECT COUNT(*) FROM epoch_rewards WHERE epoch=0"
                    ).fetchone()[0]

                # The epoch was already fully settled by the concurrent worker
                # during the fallback window. This caller must NOT credit it a
                # second time. Correct balances == exactly one payout each.
                self.assertEqual(
                    balances,
                    {"m1": 100, "m2": 200},
                    f"epoch double-credited in ADM fallback: balances={balances}, "
                    f"epoch_rewards rows={reward_rows}, result={result}",
                )
                self.assertEqual(
                    reward_rows, 2,
                    f"expected 2 epoch_rewards rows (one payout), got {reward_rows}",
                )
        finally:
            rip200.ANTI_DOUBLE_MINING_AVAILABLE = orig_adm_avail
            if orig_adm_fn is not None:
                rip200.settle_epoch_with_anti_double_mining = orig_adm_fn
            rip200.calculate_epoch_rewards_time_aged = orig_calc
            rip200.get_chain_age_years = orig_age
            rip200.get_time_aged_multiplier = orig_mult


if __name__ == "__main__":
    unittest.main()
