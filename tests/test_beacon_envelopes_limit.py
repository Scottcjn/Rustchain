import sqlite3
import unittest
from contextlib import suppress
from pathlib import Path
from uuid import uuid4

from node.beacon_anchor import (
    get_recent_envelopes,
    init_beacon_table,
    normalize_beacon_pagination,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def seed_envelopes(db_path, count=3):
    init_beacon_table(db_path)
    with sqlite3.connect(db_path) as conn:
        for idx in range(count):
            conn.execute(
                """
                INSERT INTO beacon_envelopes(
                    agent_id, kind, nonce, sig, pubkey,
                    payload_hash, payload_hash_version, anchored, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"bcn_{idx}",
                    "hello",
                    f"nonce_{idx}",
                    "00",
                    "00",
                    f"hash_{idx}",
                    2,
                    0,
                    idx,
                ),
            )
        conn.commit()


class BeaconEnvelopesLimitTest(unittest.TestCase):
    def test_normalize_beacon_pagination_clamps_lower_and_upper_bounds(self):
        self.assertEqual(normalize_beacon_pagination("-1", "-10"), (1, 0))
        self.assertEqual(normalize_beacon_pagination("0", "5"), (1, 5))
        self.assertEqual(normalize_beacon_pagination("999", "bad"), (50, 0))
        self.assertEqual(normalize_beacon_pagination("bad", None), (50, 0))

    def test_get_recent_envelopes_does_not_allow_negative_limit_bypass(self):
        db_path = REPO_ROOT / f"beacon_limit_test_{uuid4().hex}.db"
        try:
            seed_envelopes(db_path)

            rows = get_recent_envelopes(limit=-1, offset=0, db_path=db_path)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["created_at"], 2)
        finally:
            with suppress(PermissionError):
                db_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
