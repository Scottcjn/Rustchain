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

        # Disable anti-double-mining so we exercise the standard rewards path
        # (which uses the same DB connection and is already race-safe).
        orig_adm = rip200.ANTI_DOUBLE_MINING_AVAILABLE
        rip200.ANTI_DOUBLE_MINING_AVAILABLE = False

        # Patch external dependencies so the test is hermetic and fast.
        def fake_rewards(*_args, **_kwargs):
            time.sleep(0.25)  # keep the first settlement open long enough to overlap with the second
            return {"m1": 100, "m2": 200}

        rip200.calculate_epoch_rewards_time_aged = fake_rewards
        rip200.get_chain_age_years = lambda *_a, **_k: 1.0
        rip200.get_time_aged_multiplier = lambda *_a, **_k: 1.0

        try:
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
        finally:
            rip200.ANTI_DOUBLE_MINING_AVAILABLE = orig_adm


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


class TestAntiDoubleMiningSettleRace(unittest.TestCase):
    """Regression test for the double-credit race when anti-double-mining is enabled.

    settle_epoch_rip200() held BEGIN IMMEDIATE on connection A but delegated to
    settle_epoch_with_anti_double_mining() which opened connection B, bypassing
    the lock.  Two concurrent callers could both pass the already_settled check
    and double-credit miners.

    The fix marks epoch_state.settled=1 and commits BEFORE delegating to the
    anti-double-mining function, so any concurrent caller sees the flag.
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
            db.executemany(
                "INSERT INTO miner_attest_recent (miner, device_arch) VALUES (?, ?)",
                [("m1", "x86_64"), ("m2", "x86_64")],
            )
            db.execute("INSERT INTO epoch_state(epoch, settled, settled_ts) VALUES (0, 0, 0)")
            db.commit()

    def test_concurrent_settle_anti_double_mining_path(self) -> None:
        try:
            import rewards_implementation_rip200 as rip200
        except ImportError:
            import node.rewards_implementation_rip200 as rip200

        # Only run if anti-double-mining is available (the vulnerable path).
        if not rip200.ANTI_DOUBLE_MINING_AVAILABLE:
            self.skipTest("anti_double_mining not available")

        # Simulate the anti-double-mining function with a slow response.
        # The patched function mimics the real one: when existing_conn is passed,
        # it uses that connection (same transaction); otherwise it opens its own.
        call_count = [0]

        def fake_anti_double_mining(db_path, epoch, per_epoch_urtc, current_slot, existing_conn=None):
            call_count[0] += 1
            time.sleep(0.25)  # widen the race window

            if existing_conn is not None:
                db = existing_conn
                own_conn = False
            else:
                db = sqlite3.connect(db_path, timeout=10)
                own_conn = True
                db.execute("BEGIN IMMEDIATE")

            try:
                st = db.execute(
                    "SELECT settled FROM epoch_state WHERE epoch=?", (epoch,)
                ).fetchone()
                if st and int(st[0]) == 1:
                    if own_conn:
                        db.rollback()
                    return {"ok": True, "epoch": epoch, "already_settled": True}

                for miner_id, share in [("m1", 100), ("m2", 200)]:
                    db.execute(
                        "INSERT INTO balances (miner_id, amount_i64) VALUES (?, ?) "
                        "ON CONFLICT(miner_id) DO UPDATE SET amount_i64 = amount_i64 + ?",
                        (miner_id, share, share)
                    )
                    db.execute(
                        "INSERT INTO ledger (ts, epoch, miner_id, delta_i64, reason) VALUES (?, ?, ?, ?, ?)",
                        (int(time.time()), epoch, miner_id, share, f"epoch_{epoch}_reward")
                    )
                    db.execute(
                        "INSERT INTO epoch_rewards (epoch, miner_id, share_i64) VALUES (?, ?, ?)",
                        (epoch, miner_id, share)
                    )
                db.execute(
                    "INSERT OR REPLACE INTO epoch_state (epoch, settled, settled_ts) VALUES (?, 1, ?)",
                    (epoch, int(time.time()))
                )
                if own_conn:
                    db.commit()
                return {"ok": True, "epoch": epoch, "already_settled": False}
            except Exception:
                if own_conn:
                    db.rollback()
                raise
            finally:
                if own_conn:
                    db.close()

        original_fn = rip200.settle_epoch_with_anti_double_mining
        rip200.settle_epoch_with_anti_double_mining = fake_anti_double_mining

        try:
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
                t1.join(timeout=15)
                t2.join(timeout=15)

                self.assertFalse(errors, f"unexpected errors: {errors!r}")
                self.assertEqual(len(results), 2)

                with sqlite3.connect(db_path) as db:
                    rows = db.execute(
                        "SELECT miner_id, amount_i64 FROM balances ORDER BY miner_id"
                    ).fetchall()
                    self.assertEqual(rows, [("m1", 100), ("m2", 200)])

                    st = db.execute("SELECT settled FROM epoch_state WHERE epoch=0").fetchone()
                    self.assertEqual(int(st[0]), 1)

                # With the fix, the second caller is serialized by BEGIN IMMEDIATE
                # and sees already_settled before reaching the anti-double-mining
                # function.  Only one call should reach it.
                self.assertEqual(call_count[0], 1)

                already = [r.get("already_settled") for r in results if isinstance(r, dict)]
                self.assertIn(True, already)
        finally:
            rip200.settle_epoch_with_anti_double_mining = original_fn
