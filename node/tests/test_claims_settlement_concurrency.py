# SPDX-License-Identifier: MIT
"""
Regression test for #5745: concurrent claims settlement race condition.

Verifies that two concurrent calls to process_claims_batch() cannot
broadcast the same claim twice.
"""

import os
import sqlite3
import sys
import threading
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from claims_settlement import (
    process_claims_batch,
    reserve_claims_for_settlement,
    release_reserved_claims_for_settlement,
    generate_batch_id,
)


def _create_test_db(path, num_claims=5):
    """Create a test database with approved claims."""
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS claims (
            claim_id TEXT PRIMARY KEY,
            miner_id TEXT,
            epoch INTEGER,
            wallet_address TEXT,
            reward_urtc INTEGER,
            status TEXT,
            submitted_at INTEGER,
            verified_at INTEGER,
            settled_at INTEGER,
            transaction_hash TEXT,
            settlement_batch TEXT,
            rejection_reason TEXT,
            signature TEXT,
            public_key TEXT,
            ip_address TEXT,
            user_agent TEXT,
            created_at INTEGER,
            updated_at INTEGER
        )
    """)
    now = int(time.time())
    for i in range(num_claims):
        conn.execute("""
            INSERT INTO claims
            (claim_id, miner_id, epoch, wallet_address, reward_urtc,
             status, submitted_at, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'approved', ?, ?, ?)
        """, (
            f"claim-{i}",
            f"miner-{i}",
            1,
            f"RTC_wallet_{i}",
            1_000_000,
            now - i,
            now - i,
            now - i,
        ))
    conn.commit()
    conn.close()


class TestConcurrentSettlement(unittest.TestCase):
    """Regression tests for #5745."""

    def setUp(self):
        import tempfile
        fd, self.db_path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        _create_test_db(self.db_path, num_claims=5)

    def tearDown(self):
        os.unlink(self.db_path)

    def test_reserve_is_exclusive(self):
        """Two reserve calls cannot return the same claim_id."""
        batch_a = generate_batch_id(self.db_path)
        batch_b = generate_batch_id(self.db_path)

        reserved_a = reserve_claims_for_settlement(self.db_path, 10, batch_a)
        reserved_b = reserve_claims_for_settlement(self.db_path, 10, batch_b)

        ids_a = {c["claim_id"] for c in reserved_a}
        ids_b = {c["claim_id"] for c in reserved_b}

        # The second call must get zero claims because the first already
        # moved them all to 'settling'.
        self.assertTrue(len(reserved_a) > 0, "First reserve should get claims")
        self.assertEqual(len(reserved_b), 0, "Second reserve must get zero claims")
        self.assertEqual(ids_a & ids_b, set(), "No claim_id overlap allowed")

    def test_concurrent_threads_no_overlap(self):
        """Two threads calling reserve_pending_claims get disjoint sets."""
        results = {}
        errors = []

        def worker(name):
            try:
                batch = generate_batch_id(self.db_path)
                claims = reserve_claims_for_settlement(self.db_path, 10, batch)
                results[name] = [c["claim_id"] for c in claims]
            except Exception as e:
                errors.append((name, e))

        t1 = threading.Thread(target=worker, args=("w1",))
        t2 = threading.Thread(target=worker, args=("w2",))
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        self.assertEqual(errors, [], f"Workers raised errors: {errors}")

        ids_1 = set(results.get("w1", []))
        ids_2 = set(results.get("w2", []))
        self.assertEqual(ids_1 & ids_2, set(),
                         "Concurrent workers must not reserve the same claim")

        # Exactly one worker should get all 5 claims, the other zero
        total = len(ids_1) + len(ids_2)
        self.assertEqual(total, 5, f"Expected 5 total claims, got {total}")

    def test_unreserve_makes_claims_available(self):
        """release_reserved_claims_for_settlement resets 'settling' back to 'approved'."""
        batch = generate_batch_id(self.db_path)
        reserved = reserve_claims_for_settlement(self.db_path, 10, batch)
        self.assertEqual(len(reserved), 5)

        # Simulate broadcast failure — release back to approved
        release_reserved_claims_for_settlement(
            self.db_path,
            [c["claim_id"] for c in reserved],
            batch,
            "test broadcast failure",
        )

        # Now another reservation should succeed
        batch2 = generate_batch_id(self.db_path)
        reserved2 = reserve_claims_for_settlement(self.db_path, 10, batch2)
        self.assertEqual(len(reserved2), 5, "Released claims should be available again")

    def test_settling_status_blocks_second_read(self):
        """Claims in 'settling' status are invisible to get_pending_claims."""
        from claims_settlement import get_pending_claims

        batch = generate_batch_id(self.db_path)
        reserve_claims_for_settlement(self.db_path, 10, batch)

        # get_pending_claims only reads 'approved' — settling should be invisible
        pending = get_pending_claims(self.db_path, max_claims=10)
        self.assertEqual(len(pending), 0,
                         "'settling' claims must not appear in get_pending_claims")


if __name__ == "__main__":
    unittest.main()
