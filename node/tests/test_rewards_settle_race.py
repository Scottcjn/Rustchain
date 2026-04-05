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


class TestFutureEpochRejection(unittest.TestCase):
    """Settling a future epoch must be rejected outright.

    Regression test for: admin endpoint /rewards/settle accepts future epochs.
    """

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
                    ts INTEGER, epoch INTEGER, miner_id TEXT,
                    delta_i64 INTEGER, reason TEXT
                );
                CREATE TABLE epoch_rewards (
                    epoch INTEGER, miner_id TEXT, share_i64 INTEGER
                );
                CREATE TABLE miner_attest_recent (
                    miner TEXT, device_arch TEXT
                );
                """
            )
            db.execute(
                "INSERT INTO miner_attest_recent (miner, device_arch) VALUES (?, ?)",
                ("m1", "x86_64"),
            )
            db.commit()

    def test_settle_epoch_rip200_rejects_future_epoch(self) -> None:
        try:
            import rewards_implementation_rip200 as rip200
        except ImportError:
            import node.rewards_implementation_rip200 as rip200

        # Freeze "current slot" so epoch 10 is the present.
        # current_slot = (now - GENESIS) / 600  =>  epoch = slot // 144
        # For epoch 10: slot = 10 * 144 = 1440  =>  now = GENESIS + 1440*600
        fake_now = rip200.GENESIS_TIMESTAMP + 1440 * rip200.BLOCK_TIME
        rip200.current_slot = lambda: 1440  # epoch 10

        with tempfile.TemporaryDirectory() as td:
            db_path = os.path.join(td, "test.db")
            self._init_db(db_path)

            # Epoch 11 is in the future — must be rejected.
            result = rip200.settle_epoch_rip200(db_path, 11)
            self.assertFalse(result.get("ok", True))
            self.assertEqual(result.get("error"), "epoch_not_reached")
            self.assertEqual(result.get("requested"), 11)
            self.assertEqual(result.get("current_epoch"), 10)

            # Epoch 10 (current) should still be accepted (no eligible miners is a different path).
            # We just verify it doesn't get rejected with epoch_not_reached.
            result = rip200.settle_epoch_rip200(db_path, 10)
            self.assertNotEqual(result.get("error"), "epoch_not_reached")

    def test_endpoint_rejects_future_epoch(self) -> None:
        """Simulate the endpoint logic without a full Flask app."""
        try:
            import rewards_implementation_rip200 as rip200
        except ImportError:
            import node.rewards_implementation_rip200 as rip200

        # current epoch = 10
        rip200.current_slot = lambda: 1440

        # Replicate the endpoint's validation logic:
        current_epoch = rip200.slot_to_epoch(rip200.current_slot())

        # Future epoch should be rejected.
        future = current_epoch + 1
        self.assertGreater(future, current_epoch)
        # The check the endpoint performs:
        with tempfile.TemporaryDirectory() as td:
            db_path = os.path.join(td, "test.db")
            self._init_db(db_path)
            result = rip200.settle_epoch_rip200(db_path, future)
            self.assertFalse(result.get("ok", True))
            self.assertEqual(result.get("error"), "epoch_not_reached")


if __name__ == "__main__":
    unittest.main()
