#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
PoC: Epoch settlement double-credit bug (C8)

This PoC was written against an older stub contract where the ADM stub wrote
directly to a shared connection and the test itself did not call the
settlement API. The repository's settlement path (settle_epoch_rip200)
now owns the transaction lifecycle and explicitly rolls back partial ADM
writes before attempting the standard fallback. The original PoC therefore
produced a false positive: it demonstrated that "writes then raise" can
lead to double-credit only when the caller does not rollback, but it did
not exercise the actual settle_epoch_rip200 API that performs the rollback.

Update the PoC to call settle_epoch_rip200 and inject an ADM stub that
writes to the provided existing_conn and then raises. This exercises the
real rollback-before-fallback behaviour and demonstrates there is no
double-credit when the caller rolls back partial ADM writes.
"""

import os
import sys
import sqlite3
import tempfile
import time
import unittest

# These tests exercise the legacy ADM-off fallback path on purpose. Since 2026-09-05 the
# production default is RC_REQUIRE_ADM=1 (fail closed), so opt out explicitly here.
os.environ.setdefault("RC_REQUIRE_ADM", "0")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestEpochSettlementDoubleCredit(unittest.TestCase):
    """Verify that ADM failure fallback does NOT double-credit miners.

    This PoC now calls the public settlement API (settle_epoch_rip200) and
    injects an ADM stub that writes rewards to the shared connection and
    then raises. The caller (settle_epoch_rip200) must rollback the partial
    ADM writes before performing the standard-rewards fallback so that the
    final balance is a single credit only.
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test_c8.db")
        self._init_db()

    def tearDown(self):
        import shutil
        if os.path.exists(self.tmpdir):
            shutil.rmtree(self.tmpdir)

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS miner_attest_recent (
                miner TEXT PRIMARY KEY,
                device_arch TEXT,
                ts_ok INTEGER DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS balances (
                miner_id TEXT PRIMARY KEY,
                amount_i64 INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS ledger (
                ts INTEGER, epoch INTEGER, miner_id TEXT,
                delta_i64 INTEGER, reason TEXT
            );
            CREATE TABLE IF NOT EXISTS epoch_rewards (
                epoch INTEGER, miner_id TEXT, share_i64 INTEGER
            );
            CREATE TABLE IF NOT EXISTS epoch_state (
                epoch INTEGER PRIMARY KEY,
                settled INTEGER DEFAULT 0,
                settled_ts INTEGER
            );
        """)
        # Insert a single attested miner used in the PoC
        conn.execute(
            "INSERT INTO miner_attest_recent (miner, device_arch, ts_ok) VALUES (?, ?, 1)",
            ("RTC_miner_a", "x86_64"),
        )
        # Ensure an epoch_state row exists for the epoch we'll settle; the
        # real settlement logic expects the row may be absent but tests are
        # clearer when present.
        conn.execute(
            "INSERT OR IGNORE INTO epoch_state (epoch, settled, settled_ts) VALUES (?, 0, NULL)",
            (1,)
        )
        conn.commit()
        conn.close()

    def _load_module(self):
        try:
            import rewards_implementation_rip200 as rip200
        except ImportError:
            import node.rewards_implementation_rip200 as rip200
        return rip200

    def test_double_credit_on_adm_fallback(self):
        """
        Simulate: ADM writes rewards to the shared connection and then raises.
        The settlement caller must rollback ADM partial writes before the
        fallback; the final result should be a SINGLE credit per miner.
        """
        PER_EPOCH_URTC = 1_500_000

        rip200 = self._load_module()

        # Stash originals so we can restore them
        orig_adm_avail = getattr(rip200, 'ANTI_DOUBLE_MINING_AVAILABLE', False)
        orig_adm_fn = getattr(rip200, 'settle_epoch_with_anti_double_mining', None)
        orig_calc = getattr(rip200, 'calculate_epoch_rewards_time_aged', None)
        orig_age = getattr(rip200, 'get_chain_age_years', None)
        orig_mult = getattr(rip200, 'get_time_aged_multiplier', None)

        try:
            # Force the ADM branch to be taken, then fail after writing.
            rip200.ANTI_DOUBLE_MINING_AVAILABLE = True

            def adm_stub(db_path, epoch, per_epoch_urtc, current, existing_conn=None):
                """Write rewards into the provided existing_conn and then crash.

                This matches the contract of settle_epoch_with_anti_double_mining
                when the caller passes an existing connection: all writes are
                performed on the shared connection and the caller manages
                transaction/commit/rollback.
                """
                # Write to the shared connection (no commit here)
                if existing_conn is None:
                    # Defensive fallback: write to a fresh connection if none
                    c = sqlite3.connect(db_path)
                    try:
                        c.execute(
                            "INSERT INTO balances (miner_id, amount_i64) VALUES (?, ?) "
                            "ON CONFLICT(miner_id) DO UPDATE SET amount_i64 = amount_i64 + ?",
                            ("RTC_miner_a", per_epoch_urtc, per_epoch_urtc),
                        )
                        c.execute(
                            "INSERT INTO epoch_rewards (epoch, miner_id, share_i64) VALUES (?, ?, ?)",
                            (epoch, "RTC_miner_a", per_epoch_urtc),
                        )
                        c.execute(
                            "INSERT OR REPLACE INTO epoch_state (epoch, settled, settled_ts) VALUES (?, 1, ?)",
                            (epoch, int(time.time())),
                        )
                        c.commit()
                    finally:
                        c.close()
                else:
                    existing_conn.execute(
                        "INSERT INTO balances (miner_id, amount_i64) VALUES (?, ?) "
                        "ON CONFLICT(miner_id) DO UPDATE SET amount_i64 = amount_i64 + ?",
                        ("RTC_miner_a", per_epoch_urtc, per_epoch_urtc),
                    )
                    existing_conn.execute(
                        "INSERT INTO epoch_rewards (epoch, miner_id, share_i64) VALUES (?, ?, ?)",
                        (epoch, "RTC_miner_a", per_epoch_urtc),
                    )
                    # Mark epoch as settled (simulates ADM's claim/mark)
                    existing_conn.execute(
                        "INSERT OR REPLACE INTO epoch_state (epoch, settled, settled_ts) VALUES (?, 1, ?)",
                        (epoch, int(time.time())),
                    )

                # Crash after performing writes
                raise RuntimeError("simulated ADM failure after writes")

            rip200.settle_epoch_with_anti_double_mining = adm_stub

            # Stub fallback reward calculation to keep the PoC focused and
            # avoid depending on other modules.
            rip200.calculate_epoch_rewards_time_aged = lambda *_a, **_k: {"RTC_miner_a": PER_EPOCH_URTC}
            rip200.get_chain_age_years = lambda *_a, **_k: 1.0
            rip200.get_time_aged_multiplier = lambda *_a, **_k: 1.0

            # Run settlement using the module API on a connection we control so
            # the rollback in settle_epoch_rip200 can undo the ADM writes.
            conn = sqlite3.connect(self.db_path)
            try:
                result = rip200.settle_epoch_rip200(conn, epoch=1)
            finally:
                conn.close()

            # Check balances: the ADM writes must have been rolled back and
            # the standard fallback should have credited a single epoch reward.
            with sqlite3.connect(self.db_path) as db:
                bal_row = db.execute(
                    "SELECT amount_i64 FROM balances WHERE miner_id = ?",
                    ("RTC_miner_a",),
                ).fetchone()
                bal = bal_row[0] if bal_row else 0

            self.assertEqual(
                bal, PER_EPOCH_URTC,
                f"BALANCE: {bal} uRTC — expected {PER_EPOCH_URTC} uRTC"
                f"\n{'🔴 BUG: DOUBLE CREDIT — fallback wrote on top of ADM writes!' if bal != PER_EPOCH_URTC else '✅ Single credit only'}"
            )
        finally:
            # Restore
            rip200.ANTI_DOUBLE_MINING_AVAILABLE = orig_adm_avail
            if orig_adm_fn is not None:
                rip200.settle_epoch_with_anti_double_mining = orig_adm_fn
            if orig_calc is not None:
                rip200.calculate_epoch_rewards_time_aged = orig_calc
            if orig_age is not None:
                rip200.get_chain_age_years = orig_age
            if orig_mult is not None:
                rip200.get_time_aged_multiplier = orig_mult


if __name__ == '__main__':
    unittest.main(verbosity=2)
