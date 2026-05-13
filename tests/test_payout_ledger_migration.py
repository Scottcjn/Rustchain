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

        self.assertTrue(set(payout_ledger._get_columns()).issubset(columns))
        row = payout_ledger.ledger_get("old-1")
        self.assertEqual(row["id"], "old-1")
        self.assertEqual(row["bounty_id"], "bounty-1")
        self.assertEqual(row["contributor"], "alice")
        self.assertEqual(row["amount_micro_rtc"], 3500000)
        self.assertEqual(row["amount_rtc"], "3.5")
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
        self.assertEqual(row["amount_micro_rtc"], 4250000)
        self.assertEqual(row["amount_rtc"], "4.25")
        self.assertEqual(row["wallet_address"], "RTC-private")
        self.assertEqual(row["pr_url"], "https://example.test/pr/1")
        self.assertEqual(row["notes"], "created after migration")

    def test_new_writes_store_integer_micro_rtc_and_sum_exactly(self):
        payout_ledger.init_payout_ledger_tables()
        first = payout_ledger.ledger_create("bounty-1", "alice", "0.1")
        second = payout_ledger.ledger_create("bounty-2", "bob", "0.2")

        with sqlite3.connect(self.db_path) as conn:
            columns = {
                row[1]: row[2] for row in conn.execute("PRAGMA table_info(payout_ledger)")
            }
            self.assertEqual(columns["amount_micro_rtc"].upper(), "INTEGER")
            self.assertNotIn("amount_rtc", columns)
            total_micro = conn.execute(
                "SELECT SUM(amount_micro_rtc) FROM payout_ledger"
            ).fetchone()[0]

        self.assertEqual(total_micro, 300000)
        self.assertEqual(payout_ledger.ledger_get(first)["amount_rtc"], "0.1")
        self.assertEqual(payout_ledger.ledger_get(second)["amount_rtc"], "0.2")
        self.assertEqual(
            payout_ledger.ledger_summary()["queued"],
            {"count": 2, "total_micro_rtc": 300000, "total_rtc": "0.3"},
        )

    def test_amount_rtc_rejects_more_than_micro_precision(self):
        payout_ledger.init_payout_ledger_tables()

        with self.assertRaises(ValueError):
            payout_ledger.ledger_create("bounty-1", "alice", "0.0000001")


if __name__ == "__main__":
    unittest.main()
