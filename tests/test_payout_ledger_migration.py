import os
import gc
import sqlite3
import tempfile
import unittest

import payout_ledger


class TestPayoutLedgerMigration(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.tmp.name
        self.tmp.close()
        self.original_db_path = payout_ledger.DB_PATH
        payout_ledger.DB_PATH = self.db_path

    def tearDown(self):
        payout_ledger.DB_PATH = self.original_db_path
        gc.collect()
        try:
            os.unlink(self.db_path)
        except PermissionError:
            # Windows can briefly hold sqlite handles after failed assertions.
            pass

    def _create_v1_table(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE payout_ledger (
                    id TEXT PRIMARY KEY,
                    bounty_id TEXT NOT NULL,
                    contributor TEXT NOT NULL,
                    amount_rtc REAL NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'queued',
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                )
            """)
            conn.execute(
                "INSERT INTO payout_ledger "
                "(id, bounty_id, contributor, amount_rtc, status, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("old-1", "bounty-1", "alice", 3.5, "pending", 100, 200),
            )

    def test_init_migrates_old_table_and_preserves_existing_rows(self):
        self._create_v1_table()

        payout_ledger.init_payout_ledger_tables()

        with sqlite3.connect(self.db_path) as conn:
            columns = {
                row[1] for row in conn.execute("PRAGMA table_info(payout_ledger)")
            }

        self.assertEqual(columns, set(payout_ledger._get_columns()))
        row = payout_ledger.ledger_get("old-1")
        self.assertEqual(row["id"], "old-1")
        self.assertEqual(row["bounty_id"], "bounty-1")
        self.assertEqual(row["contributor"], "alice")
        self.assertEqual(row["amount_rtc"], 3.5)
        self.assertEqual(row["status"], "pending")
        self.assertEqual(row["created_at"], 100)
        self.assertEqual(row["updated_at"], 200)
        self.assertIn("tx_hash", row)
        self.assertIn("wallet_address", row)

    def test_init_migration_is_idempotent_and_new_writes_work(self):
        self._create_v1_table()

        payout_ledger.init_payout_ledger_tables()
        payout_ledger.init_payout_ledger_tables()
        new_id = payout_ledger.ledger_create(
            "bounty-2",
            "bob",
            4.25,
            bounty_title="Schema fix",
            wallet_address="RTC-private",
            pr_url="https://example.test/pr/1",
            notes="created after migration",
        )

        row = payout_ledger.ledger_get(new_id)
        self.assertEqual(row["bounty_id"], "bounty-2")
        self.assertEqual(row["bounty_title"], "Schema fix")
        self.assertEqual(row["contributor"], "bob")
        self.assertEqual(row["wallet_address"], "RTC-private")
        self.assertEqual(row["pr_url"], "https://example.test/pr/1")
        self.assertEqual(row["notes"], "created after migration")


if __name__ == "__main__":
    unittest.main()
