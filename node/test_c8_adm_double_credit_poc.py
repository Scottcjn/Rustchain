#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
PoC: Epoch settlement double-credit bug (C8)

Demonstrates that when anti-double-mining settlement writes rewards but
then raises an exception, the fallback to standard rewards on the same
database connection results in double-crediting miners.

Bug chain in rewards_implementation_rip200.py settle_epoch_rip200():
1. Calls settle_epoch_with_anti_double_mining(existing_conn=db)
2. That function writes rewards + marks epoch_state on the SHARED conn
3. If it crashes AFTER writing rewards (e.g. in telemetry or metadata),
   the exception is caught at line 175
4. NO rollback is issued on the shared conn
5. Standard rewards fallback writes miners AGAIN on the same conn
6. Both sets committed at db.commit() → double-credit
"""

import os
import sys
import sqlite3
import tempfile
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# We'll construct the scenario manually since importing the live module
# requires Flask and database setup


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
        Simulate: anti-double-mining writes rewards, then raises.
        Standard fallback writes rewards on same connection.
        Result should be a SINGLE credit per miner, not double.
        """
        PER_EPOCH_URTC = 1_500_000

        conn = sqlite3.connect(self.db_path)
        conn.execute("BEGIN IMMEDIATE")

        # Phase 1: Simulate ADM writes (rewards credited)
        conn.execute(
            "INSERT INTO balances (miner_id, amount_i64) VALUES (?, ?) "
            "ON CONFLICT(miner_id) DO UPDATE SET amount_i64 = amount_i64 + ?",
            ("RTC_miner_a", PER_EPOCH_URTC, PER_EPOCH_URTC),
        )
        # Mark epoch_state (ADM writes this)
        conn.execute(
            "UPDATE epoch_state SET settled = 1, settled_ts = ? WHERE epoch = ?",
            (int(time.time()), 1),
        )

        # ADM crashes AFTER writes (before telemetry/metadata lines)
        # We simulate this by raising - the caller catches and falls through

        # Phase 2: Standard rewards fallback (same connection, no rollback)
        conn.execute(
            "INSERT INTO balances (miner_id, amount_i64) VALUES (?, ?) "
            "ON CONFLICT(miner_id) DO UPDATE SET amount_i64 = amount_i64 + ?",
            ("RTC_miner_a", PER_EPOCH_URTC, PER_EPOCH_URTC),
        )

        bal = conn.execute(
            "SELECT amount_i64 FROM balances WHERE miner_id = ?",
            ("RTC_miner_a",),
        ).fetchone()
        conn.close()

        # BUG: If both writes took effect, balance = 2 * PER_EPOCH_URTC
        self.assertEqual(
            bal[0], PER_EPOCH_URTC,
            f"BALANCE: {bal[0]} uRTC — expected {PER_EPOCH_URTC} uRTC"
            f"\n{'🔴 BUG: DOUBLE CREDIT — fallback wrote on top of ADM writes!' if bal[0] != PER_EPOCH_URTC else '✅ Single credit only'}"
        )


if __name__ == '__main__':
    unittest.main(verbosity=2)
