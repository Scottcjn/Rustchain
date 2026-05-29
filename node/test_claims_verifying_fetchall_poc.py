"""
PoC: get_verifying_claims() had no LIMIT on its SQL query.
fetchall() would materialize every 'verifying' claim into RAM on each
settlement cycle, enabling OOM DoS by flooding the claims table with
submissions that remain stuck in 'verifying'.

Before fix: query had no LIMIT clause.
After fix:  query adds LIMIT 500 (_VERIFYING_CLAIMS_LIMIT).
"""
import sqlite3
import time
import unittest
import tempfile
import os

from claims_settlement import get_verifying_claims, _VERIFYING_CLAIMS_LIMIT


def _make_db(path: str) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS claims (
                claim_id TEXT PRIMARY KEY,
                miner_id TEXT,
                epoch INTEGER,
                wallet_address TEXT,
                reward_urtc INTEGER,
                submitted_at INTEGER,
                status TEXT
            )
        """)
        conn.commit()


_claim_counter = 0


def _insert_claims(path: str, count: int, status: str = "verifying", ts_offset: int = -600):
    global _claim_counter
    ts = int(time.time()) + ts_offset
    with sqlite3.connect(path) as conn:
        for i in range(count):
            conn.execute(
                "INSERT INTO claims VALUES (?, ?, ?, ?, ?, ?, ?)",
                (f"claim_{_claim_counter}", f"miner_{_claim_counter}", 1, f"RTC{'0' * 40}", 1000, ts - i, status)
            )
            _claim_counter += 1
        conn.commit()


class TestVerifyingClaimsLimit(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.tmp.name
        self.tmp.close()
        _make_db(self.db_path)

    def tearDown(self):
        os.unlink(self.db_path)

    def test_respects_limit_when_many_rows(self):
        """With more rows than _VERIFYING_CLAIMS_LIMIT, only the limit is returned."""
        over_limit = _VERIFYING_CLAIMS_LIMIT + 100
        _insert_claims(self.db_path, over_limit)
        result = get_verifying_claims(self.db_path, older_than_seconds=300)
        self.assertLessEqual(len(result), _VERIFYING_CLAIMS_LIMIT,
                             f"Expected at most {_VERIFYING_CLAIMS_LIMIT} rows, got {len(result)}")

    def test_returns_all_when_under_limit(self):
        """With fewer rows than the limit, all are returned."""
        count = 10
        _insert_claims(self.db_path, count)
        result = get_verifying_claims(self.db_path, older_than_seconds=300)
        self.assertEqual(len(result), count)

    def test_filters_by_status(self):
        """Only 'verifying' claims are returned."""
        _insert_claims(self.db_path, 5, status="verifying")
        _insert_claims(self.db_path, 3, status="approved")
        result = get_verifying_claims(self.db_path, older_than_seconds=300)
        self.assertEqual(len(result), 5)

    def test_filters_by_age(self):
        """Claims newer than older_than_seconds are excluded."""
        _insert_claims(self.db_path, 5, status="verifying", ts_offset=-600)
        _insert_claims(self.db_path, 3, status="verifying", ts_offset=600)
        result = get_verifying_claims(self.db_path, older_than_seconds=300)
        self.assertEqual(len(result), 5)

    def test_empty_table(self):
        result = get_verifying_claims(self.db_path, older_than_seconds=300)
        self.assertEqual(result, [])

    def test_result_shape(self):
        _insert_claims(self.db_path, 1)
        result = get_verifying_claims(self.db_path, older_than_seconds=300)
        self.assertEqual(len(result), 1)
        row = result[0]
        self.assertIn("claim_id", row)
        self.assertIn("miner_id", row)
        self.assertIn("epoch", row)
        self.assertIn("wallet_address", row)
        self.assertIn("reward_urtc", row)
        self.assertIn("submitted_at", row)


if __name__ == "__main__":
    unittest.main()
