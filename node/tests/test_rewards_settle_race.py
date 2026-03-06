import os
import sqlite3
import tempfile
import threading
import time
import unittest


class TestRewardsSettleRace(unittest.TestCase):
    def _init_db(self, path: str) -> None:
        with sqlite3.connect(path) as db:
            db.executescript(
                """
                CREATE TABLE epoch_state (
                    epoch INTEGER PRIMARY KEY,
                    settled INTEGER DEFAULT 0,
                    settled_ts INTEGER
                );

                CREATE TABLE balances (
                    miner_id TEXT PRIMARY KEY,
                    amount_i64 INTEGER NOT NULL
                );

                CREATE TABLE ledger (
                    ts INTEGER,
                    epoch INTEGER,
                    miner_id TEXT,
                    delta_i64 INTEGER,
                    reason TEXT
                );

                CREATE TABLE epoch_rewards (
                    epoch INTEGER,
                    miner_id TEXT,
                    share_i64 INTEGER
                );

                CREATE TABLE miner_attest_recent (
                    miner TEXT,
                    device_arch TEXT
                );
                """
            )
            db.executemany(
                "INSERT INTO miner_attest_recent (miner, device_arch) VALUES (?, ?)",
                [("m1", "x86_64"), ("m2", "x86_64")],
            )
            db.execute("INSERT INTO epoch_state(epoch, settled, settled_ts) VALUES (0, 0, 0)")
            db.commit()

    def test_concurrent_settle_is_idempotent(self) -> None:
        # Import inside the test so any env var/test patching stays scoped.
        try:
            import rewards_implementation_rip200 as rip200
        except ImportError:
            import node.rewards_implementation_rip200 as rip200

        # Patch external dependencies so the test is hermetic and fast.
        def fake_rewards(*_args, **_kwargs):
            time.sleep(0.25)  # keep the first settlement open long enough to overlap with the second
            return {"m1": 100, "m2": 200}

        rip200.calculate_epoch_rewards_time_aged = fake_rewards
        rip200.get_chain_age_years = lambda *_a, **_k: 1.0
        rip200.get_time_aged_multiplier = lambda *_a, **_k: 1.0

        with tempfile.TemporaryDirectory() as td:
            db_path = os.path.join(td, "test.db")
            self._init_db(db_path)

            results = []
            errors = []

            def worker():
                try:
                    results.append(rip200.settle_epoch_rip200(db_path, 0))
                except Exception as e:
                    errors.append(e)

            t1 = threading.Thread(target=worker)
            t2 = threading.Thread(target=worker)
            t1.start()
            t2.start()
            t1.join(timeout=10)
            t2.join(timeout=10)

            self.assertFalse(errors, f"unexpected errors: {errors!r}")
            self.assertEqual(len(results), 2)

            with sqlite3.connect(db_path) as db:
                # Only one settlement should be applied.
                rows = db.execute("SELECT miner_id, amount_i64 FROM balances ORDER BY miner_id").fetchall()
                self.assertEqual(rows, [("m1", 100), ("m2", 200)])

                rewards_rows = db.execute("SELECT epoch, miner_id, share_i64 FROM epoch_rewards ORDER BY miner_id").fetchall()
                self.assertEqual(rewards_rows, [(0, "m1", 100), (0, "m2", 200)])

                st = db.execute("SELECT settled FROM epoch_state WHERE epoch=0").fetchone()
                self.assertEqual(int(st[0]), 1)

            # One of the calls should observe "already_settled".
            already = [r.get("already_settled") for r in results if isinstance(r, dict)]
            self.assertIn(True, already)


if __name__ == "__main__":
    unittest.main()
