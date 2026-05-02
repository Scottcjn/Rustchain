#!/usr/bin/env python3
"""
Tests for HIGH-SYNC-2: Peer sync must not allow balance inflation.

Demonstrates that apply_sync_payload() rejects balance changes (both
increases and decreases) from remote peers for wallets that already
have a local balance, preventing arbitrary fund inflation.
"""

import os
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rustchain_sync import RustChainSyncManager


class TestSyncBalanceInflation(unittest.TestCase):
    """HIGH-SYNC-2: Peer sync must reject balance modifications."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db_path = self.tmp.name

        # Create the balances table matching the production schema
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE balances (
                    miner_id TEXT PRIMARY KEY,
                    amount_i64 INTEGER NOT NULL DEFAULT 0
                )
            """)
            # Seed a local balance
            conn.execute(
                "INSERT INTO balances (miner_id, amount_i64) VALUES (?, ?)",
                ("miner-alice", 5_000_000),  # 5 RTC
            )
            conn.commit()

        self.sync = RustChainSyncManager(self.db_path, "test_admin_key")
        # Clear schema cache so it picks up our freshly created table
        self.sync._schema_cache.clear()

    def tearDown(self):
        try:
            os.unlink(self.db_path)
        except PermissionError:
            pass

    def _get_balance(self, miner_id: str) -> int:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT amount_i64 FROM balances WHERE miner_id = ?",
                (miner_id,),
            ).fetchone()
            return row[0] if row else 0

    # -- Tests ---------------------------------------------------------------

    def test_balance_increase_rejected(self):
        """Peers must NOT be able to inflate a wallet's balance.

        Before the fix, only decreases were rejected — increases sailed
        through, allowing any peer to set any wallet to any value.
        """
        original = self._get_balance("miner-alice")
        self.assertEqual(original, 5_000_000)

        # Malicious peer syncs a higher balance
        self.sync.apply_sync_payload(
            "balances",
            [
                {"miner_id": "miner-alice", "amount_i64": 999_000_000},  # 999 RTC
            ],
        )

        after = self._get_balance("miner-alice")
        self.assertEqual(after, 5_000_000, "Balance must not increase via peer sync")

    def test_balance_decrease_still_rejected(self):
        """Existing protection against decreases must still work."""
        self.sync.apply_sync_payload(
            "balances",
            [
                {"miner_id": "miner-alice", "amount_i64": 1_000_000},  # 1 RTC
            ],
        )

        after = self._get_balance("miner-alice")
        self.assertEqual(after, 5_000_000, "Balance must not decrease via peer sync")

    def test_new_wallet_from_sync_allowed(self):
        """New wallets (no local row yet) CAN be created via sync.

        This allows initial balance propagation for newly registered miners.
        """
        self.sync.apply_sync_payload(
            "balances",
            [
                {"miner_id": "miner-bob", "amount_i64": 2_000_000},  # 2 RTC
            ],
        )

        bob_balance = self._get_balance("miner-bob")
        self.assertEqual(bob_balance, 2_000_000, "New wallet should be created via sync")

    def test_unchanged_balance_passes(self):
        """Sync with identical balance value should succeed (no-op upsert)."""
        self.sync.apply_sync_payload(
            "balances",
            [
                {"miner_id": "miner-alice", "amount_i64": 5_000_000},
            ],
        )

        after = self._get_balance("miner-alice")
        self.assertEqual(after, 5_000_000, "Identical balance should not be rejected")


if __name__ == "__main__":
    unittest.main()
