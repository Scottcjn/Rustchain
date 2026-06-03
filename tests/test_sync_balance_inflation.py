import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "node"))
from rustchain_sync import RustChainSyncManager


def _init_balances_db(db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE balances (
                miner_id TEXT PRIMARY KEY,
                amount_i64 INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.execute(
            "INSERT INTO balances (miner_id, amount_i64) VALUES (?, ?)",
            ("miner-alice", 5_000_000),
        )
        conn.commit()


def _balance_row(db_path: Path, miner_id: str):
    with sqlite3.connect(db_path) as conn:
        return conn.execute(
            "SELECT amount_i64 FROM balances WHERE miner_id = ?",
            (miner_id,),
        ).fetchone()


class TestSyncBalanceInflation(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmpdir.name) / "sync.db"
        _init_balances_db(self.db_path)
        self.sync = RustChainSyncManager(str(self.db_path), "test_admin_key")

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_rejects_nonzero_balance_for_unknown_wallet(self):
        self.assertTrue(
            self.sync.apply_sync_payload(
                "balances",
                [{"miner_id": "miner-bob", "amount_i64": 2_000_000}],
            )
        )

        self.assertIsNone(_balance_row(self.db_path, "miner-bob"))

    def test_allows_zero_balance_placeholder_for_unknown_wallet(self):
        self.assertTrue(
            self.sync.apply_sync_payload(
                "balances",
                [{"miner_id": "miner-bob", "amount_i64": 0}],
            )
        )

        row = _balance_row(self.db_path, "miner-bob")
        self.assertIsNotNone(row)
        self.assertEqual(row[0], 0)


if __name__ == "__main__":
    unittest.main()
