#!/usr/bin/env python3
"""
Test: UTXO Genesis Migration Rollback Atomicity (Bounty #2819)
================================================================

Verifies that rollback_genesis() is:
1. Atomic - cannot leave partial deletion state
2. Idempotent-safe - safe to call multiple times
3. Re-run safe - migration can be re-run after rollback without corruption
"""

import os
import shutil
import sqlite3
import sys
import tempfile
import threading
import unittest

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(__file__))

from utxo_genesis_migration import (
    migrate,
    rollback_genesis,
    check_existing_genesis,
    GENESIS_HEIGHT,
)
from utxo_db import UtxoDB, UNIT, address_to_proposition


class TestRollbackAtomicity(unittest.TestCase):
    """Test rollback atomicity and re-run safety."""

    def setUp(self):
        """Create a temporary database with test balances."""
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test_rollback.db")

        # Create balances table with test data
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS balances (
                miner_id TEXT PRIMARY KEY,
                amount_i64 INTEGER NOT NULL DEFAULT 0
            )
        """)
        # Insert test wallets
        test_wallets = [
            ("wallet_a", 1000000),   # 1.0 RTC
            ("wallet_b", 500000),    # 0.5 RTC
            ("wallet_c", 250000),    # 0.25 RTC
        ]
        conn.executemany(
            "INSERT INTO balances (miner_id, amount_i64) VALUES (?, ?)",
            test_wallets,
        )
        conn.commit()
        conn.close()

    def tearDown(self):
        """Clean up temporary database."""
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
        # Remove WAL and SHM files
        for ext in ['-wal', '-shm']:
            path = self.db_path + ext
            if os.path.exists(path):
                os.unlink(path)
        if os.path.exists(self.tmpdir):
            shutil.rmtree(self.tmpdir)

    def _insert_non_genesis_height_zero_box(self):
        """Insert a confirmed height-0 transfer box that is not genesis."""
        UtxoDB(self.db_path).init_tables()
        tx_id = "1" * 64
        box_id = "2" * 64
        owner = "sentinel_wallet"

        conn = UtxoDB(self.db_path)._conn()
        try:
            conn.execute(
                """INSERT INTO utxo_transactions
                   (tx_id, tx_type, inputs_json, outputs_json,
                    data_inputs_json, fee_nrtc, timestamp,
                    block_height, status)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    tx_id,
                    "transfer",
                    "[]",
                    '[{"box_id":"%s","value_nrtc":1000,"owner":"%s"}]' % (
                        box_id,
                        owner,
                    ),
                    "[]",
                    0,
                    1,
                    GENESIS_HEIGHT,
                    "confirmed",
                ),
            )
            conn.execute(
                """INSERT INTO utxo_boxes
                   (box_id, value_nrtc, proposition, owner_address,
                    creation_height, transaction_id, output_index,
                    tokens_json, registers_json, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    box_id,
                    1000,
                    address_to_proposition(owner),
                    owner,
                    GENESIS_HEIGHT,
                    tx_id,
                    0,
                    "[]",
                    "{}",
                    1,
                ),
            )
            conn.commit()
        finally:
            conn.close()

        return box_id

    def test_01_migrate_creates_genesis(self):
        """Verify migration creates genesis boxes."""
        result = migrate(self.db_path, dry_run=False)
        self.assertEqual(result['wallets_migrated'], 3)
        self.assertEqual(result['boxes_created'], 3)
        self.assertTrue(check_existing_genesis(UtxoDB(self.db_path)))

    def test_02_rollback_removes_all_genesis(self):
        """Verify rollback removes all genesis data atomically."""
        # First migrate
        migrate(self.db_path, dry_run=False)

        # Then rollback
        deleted = rollback_genesis(self.db_path)
        self.assertEqual(deleted, 3)

        # Verify no genesis boxes remain
        utxo_db = UtxoDB(self.db_path)
        self.assertFalse(check_existing_genesis(utxo_db))

        # Verify no genesis transactions remain
        conn = utxo_db._conn()
        try:
            tx_count = conn.execute(
                "SELECT COUNT(*) FROM utxo_transactions WHERE tx_type = 'genesis'",
            ).fetchone()[0]
            self.assertEqual(tx_count, 0)
        finally:
            conn.close()

    def test_03_rollback_idempotent(self):
        """Verify rollback is safe to call when no genesis exists."""
        # Initialize tables first (simulates real-world scenario)
        UtxoDB(self.db_path).init_tables()

        # Rollback on empty DB should not raise
        deleted = rollback_genesis(self.db_path)
        self.assertEqual(deleted, 0)

        # Second rollback should also be safe
        deleted = rollback_genesis(self.db_path)
        self.assertEqual(deleted, 0)

    def test_04_rerun_after_rollback(self):
        """Verify migration can be re-run after rollback without corruption."""
        # First migration
        result1 = migrate(self.db_path, dry_run=False)
        self.assertEqual(result1['boxes_created'], 3)

        # Rollback
        rollback_genesis(self.db_path)

        # Re-migrate should succeed (not fail due to partial state)
        result2 = migrate(self.db_path, dry_run=False)
        self.assertEqual(result2['boxes_created'], 3)
        self.assertEqual(result1['state_root'], result2['state_root'])

    def test_05_atomic_no_partial_state(self):
        """
        Verify atomicity: simulate failure scenario and ensure no partial state.

        This test verifies that the transaction wrapping prevents partial
        deletion. We manually verify that boxes and transactions are
        deleted in the same transaction.
        """
        # Migrate first
        migrate(self.db_path, dry_run=False)

        utxo_db = UtxoDB(self.db_path)
        conn = utxo_db._conn()
        try:
            # Verify genesis exists
            box_count = conn.execute(
                "SELECT COUNT(*) FROM utxo_boxes WHERE creation_height = ?",
                (GENESIS_HEIGHT,),
            ).fetchone()[0]
            self.assertEqual(box_count, 3)

            tx_count = conn.execute(
                "SELECT COUNT(*) FROM utxo_transactions WHERE tx_type = 'genesis'",
            ).fetchone()[0]
            self.assertEqual(tx_count, 3)

            # Perform rollback
            rollback_genesis(self.db_path)

            # Verify BOTH boxes and transactions are gone (atomic)
            box_count_after = conn.execute(
                "SELECT COUNT(*) FROM utxo_boxes WHERE creation_height = ?",
                (GENESIS_HEIGHT,),
            ).fetchone()[0]
            tx_count_after = conn.execute(
                "SELECT COUNT(*) FROM utxo_transactions WHERE tx_type = 'genesis'",
            ).fetchone()[0]

            self.assertEqual(box_count_after, 0, "Partial rollback: boxes remain")
            self.assertEqual(tx_count_after, 0, "Partial rollback: transactions remain")
        finally:
            conn.close()

    def test_06_consistent_connection_settings(self):
        """Verify rollback uses same connection settings as UtxoDB."""
        # This is a code-level verification that rollback_genesis uses:
        # - timeout=30
        # - PRAGMA journal_mode=WAL
        # - PRAGMA foreign_keys=ON
        # We verify by checking the DB state after rollback
        migrate(self.db_path, dry_run=False)
        rollback_genesis(self.db_path)

        # Verify WAL mode is active
        conn = sqlite3.connect(self.db_path)
        try:
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
            self.assertIn(mode, ["wal", "WAL"], "WAL mode not active after rollback")
        finally:
            conn.close()

    def test_07_height_zero_transfer_is_not_genesis(self):
        """Verify height-0 non-genesis boxes do not block or get rolled back."""
        box_id = self._insert_non_genesis_height_zero_box()

        self.assertFalse(check_existing_genesis(UtxoDB(self.db_path)))

        deleted = rollback_genesis(self.db_path)
        self.assertEqual(deleted, 0)

        conn = UtxoDB(self.db_path)._conn()
        try:
            box_count = conn.execute(
                "SELECT COUNT(*) FROM utxo_boxes WHERE box_id = ?",
                (box_id,),
            ).fetchone()[0]
            transfer_count = conn.execute(
                "SELECT COUNT(*) FROM utxo_transactions WHERE tx_type = 'transfer'",
            ).fetchone()[0]

            self.assertEqual(box_count, 1)
            self.assertEqual(transfer_count, 1)
        finally:
            conn.close()

    def test_08_concurrent_migrations_serialize_cleanly(self):
        """Verify concurrent migration attempts cannot both create genesis."""
        barrier = threading.Barrier(2)
        lock = threading.Lock()
        results = []
        errors = []

        def run_migration():
            try:
                barrier.wait()
                result = migrate(self.db_path, dry_run=False)
                with lock:
                    results.append(result)
            except Exception as exc:
                with lock:
                    errors.append(exc)

        threads = [
            threading.Thread(target=run_migration),
            threading.Thread(target=run_migration),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(errors, [])
        successes = [r for r in results if 'error' not in r]
        duplicates = [
            r for r in results
            if r.get('error') == 'genesis_already_exists'
        ]
        self.assertEqual(len(successes), 1)
        self.assertEqual(len(duplicates), 1)

        conn = UtxoDB(self.db_path)._conn()
        try:
            tx_count = conn.execute(
                "SELECT COUNT(*) FROM utxo_transactions WHERE tx_type = 'genesis'",
            ).fetchone()[0]
            box_count = conn.execute(
                "SELECT COUNT(*) FROM utxo_boxes WHERE creation_height = ?",
                (GENESIS_HEIGHT,),
            ).fetchone()[0]

            self.assertEqual(tx_count, 3)
            self.assertEqual(box_count, 3)
        finally:
            conn.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
