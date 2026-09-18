#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
Regression Test: Epoch settlement double-credit on ADM failure (C8)

Demonstrates and verifies that when anti-double-mining settlement writes
partial rewards on the shared connection and then raises an exception,
settle_epoch_rip200() issues a db.rollback() before proceeding to the
standard fallback path, preventing duplicate credit to miners.
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
    """Verify that ADM failure fallback does NOT double-credit miners."""

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
        conn.execute(
            "INSERT INTO miner_attest_recent (miner, device_arch, ts_ok) VALUES (?, ?, 1)",
            ("RTC_miner_a", "x86_64"),
        )
        conn.commit()
        conn.close()

    def test_double_credit_on_adm_fallback(self):
        """
        Verify settle_epoch_rip200 rolls back partial ADM writes before standard fallback.
        When ADM writes partial rewards on the shared connection and then raises,
        settle_epoch_rip200 must roll back those uncommitted writes so that the
        standard path produces a single credit, not double.
        """
        PER_EPOCH_URTC = 1_500_000
        EPOCH = 0

        import node.rewards_implementation_rip200 as rip200

        orig_adm_avail = rip200.ANTI_DOUBLE_MINING_AVAILABLE
        orig_adm_fn = getattr(rip200, "settle_epoch_with_anti_double_mining", None)
        orig_calc = rip200.calculate_epoch_rewards_time_aged
        orig_age = rip200.get_chain_age_years
        orig_mult = rip200.get_time_aged_multiplier

        rip200.ANTI_DOUBLE_MINING_AVAILABLE = True

        def crashing_adm(db_path, epoch, budget, current_slot, existing_conn=None):
            # Simulate ADM writing partial rewards to the shared connection, then crashing
            conn = existing_conn if existing_conn is not None else sqlite3.connect(db_path)
            conn.execute(
                "INSERT INTO balances (miner_id, amount_i64) VALUES (?, ?) "
                "ON CONFLICT(miner_id) DO UPDATE SET amount_i64 = amount_i64 + ?",
                ("RTC_miner_a", PER_EPOCH_URTC, PER_EPOCH_URTC),
            )
            conn.execute(
                "INSERT INTO ledger (ts, epoch, miner_id, delta_i64, reason) VALUES (?, ?, ?, ?, ?)",
                (int(time.time()), epoch, "RTC_miner_a", PER_EPOCH_URTC, "adm_partial_write"),
            )
            raise RuntimeError("simulated ADM crash after partial write")

        rip200.settle_epoch_with_anti_double_mining = crashing_adm
        rip200.calculate_epoch_rewards_time_aged = lambda *_a, **_k: {"RTC_miner_a": PER_EPOCH_URTC}
        rip200.get_chain_age_years = lambda *_a, **_k: 1.0
        rip200.get_time_aged_multiplier = lambda *_a, **_k: 1.0

        try:
            # Under RC_REQUIRE_ADM=0 (fallback enabled), settle_epoch_rip200 must rollback
            # the crashing ADM partial write and credit exactly once via standard path.
            old_req = os.environ.get("RC_REQUIRE_ADM")
            os.environ["RC_REQUIRE_ADM"] = "0"
            try:
                res = rip200.settle_epoch_rip200(self.db_path, epoch=EPOCH)
            finally:
                if old_req is None:
                    os.environ.pop("RC_REQUIRE_ADM", None)
                else:
                    os.environ["RC_REQUIRE_ADM"] = old_req

            self.assertTrue(res.get("ok"), f"settlement failed: {res}")

            conn = sqlite3.connect(self.db_path)
            bal = conn.execute(
                "SELECT amount_i64 FROM balances WHERE miner_id = ?",
                ("RTC_miner_a",),
            ).fetchone()
            ledger_rows = conn.execute(
                "SELECT delta_i64, reason FROM ledger WHERE epoch = ?",
                (EPOCH,),
            ).fetchall()
            conn.close()

            self.assertIsNotNone(bal, "miner balance row missing")
            self.assertEqual(
                bal[0], PER_EPOCH_URTC,
                f"BALANCE: {bal[0]} uRTC — expected {PER_EPOCH_URTC} uRTC (single credit only)",
            )
            # Ensure the ADM partial ledger write was rolled back and only standard remains
            self.assertEqual(len(ledger_rows), 1, f"expected 1 ledger row, got {ledger_rows}")
            self.assertEqual(ledger_rows[0][1], f"epoch_{EPOCH}_reward")
        finally:
            rip200.ANTI_DOUBLE_MINING_AVAILABLE = orig_adm_avail
            rip200.settle_epoch_with_anti_double_mining = orig_adm_fn
            rip200.calculate_epoch_rewards_time_aged = orig_calc
            rip200.get_chain_age_years = orig_age
            rip200.get_time_aged_multiplier = orig_mult


if __name__ == '__main__':
    unittest.main(verbosity=2)
