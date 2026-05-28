import importlib.util
from contextlib import closing
import gc
import os
import sqlite3
import sys
import tempfile
import types
import unittest


NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULE_PATH = os.path.join(NODE_DIR, "rustchain_v2_integrated_v2.2.1_rip200.py")


class _NoopMetric:
    def __init__(self, *args, **kwargs):
        pass

    def inc(self, *args, **kwargs):
        pass

    def dec(self, *args, **kwargs):
        pass

    def set(self, *args, **kwargs):
        pass

    def observe(self, *args, **kwargs):
        pass

    def labels(self, *args, **kwargs):
        return self


class TestIntegratedBalanceScale(unittest.TestCase):
    @staticmethod
    def _cleanup_tempdir(tmpdir):
        gc.collect()
        tmpdir.cleanup()

    @classmethod
    def setUpClass(cls):
        cls._import_tmp = tempfile.TemporaryDirectory()
        cls._prev_db_path = os.environ.get("RUSTCHAIN_DB_PATH")
        cls._prev_admin_key = os.environ.get("RC_ADMIN_KEY")
        os.environ["RUSTCHAIN_DB_PATH"] = os.path.join(cls._import_tmp.name, "import.db")
        os.environ["RC_ADMIN_KEY"] = "0" * 32

        if NODE_DIR not in sys.path:
            sys.path.insert(0, NODE_DIR)

        prev_prometheus = sys.modules.get("prometheus_client")
        fake_prometheus = types.ModuleType("prometheus_client")
        fake_prometheus.Counter = _NoopMetric
        fake_prometheus.Gauge = _NoopMetric
        fake_prometheus.Histogram = _NoopMetric
        fake_prometheus.generate_latest = lambda *args, **kwargs: b""
        fake_prometheus.CONTENT_TYPE_LATEST = "text/plain"
        sys.modules["prometheus_client"] = fake_prometheus

        spec = importlib.util.spec_from_file_location(
            "rustchain_integrated_balance_scale_test",
            MODULE_PATH,
        )
        cls.mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(cls.mod)
        finally:
            if prev_prometheus is None:
                sys.modules.pop("prometheus_client", None)
            else:
                sys.modules["prometheus_client"] = prev_prometheus

    @classmethod
    def tearDownClass(cls):
        if cls._prev_db_path is None:
            os.environ.pop("RUSTCHAIN_DB_PATH", None)
        else:
            os.environ["RUSTCHAIN_DB_PATH"] = cls._prev_db_path
        if cls._prev_admin_key is None:
            os.environ.pop("RC_ADMIN_KEY", None)
        else:
            os.environ["RC_ADMIN_KEY"] = cls._prev_admin_key
        sys.modules.pop("rustchain_integrated_balance_scale_test", None)
        cls.mod = None
        cls._cleanup_tempdir(cls._import_tmp)

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self._tmp.name, "scale.db")
        self._prev_module_db = self.mod.DB_PATH
        self._prev_utxo_dual_write = self.mod.UTXO_DUAL_WRITE
        self._prev_utxo_db = self.mod.UtxoDB
        self.mod.DB_PATH = self.db_path
        self.mod.UTXO_DUAL_WRITE = False
        self._init_db()

    def tearDown(self):
        self.mod.DB_PATH = self._prev_module_db
        self.mod.UTXO_DUAL_WRITE = self._prev_utxo_dual_write
        self.mod.UtxoDB = self._prev_utxo_db
        self._cleanup_tempdir(self._tmp)

    def _init_db(self):
        with closing(sqlite3.connect(self.db_path)) as db:
            db.executescript(
                """
                CREATE TABLE epoch_state (
                    epoch INTEGER PRIMARY KEY,
                    settled INTEGER DEFAULT 0,
                    settled_ts INTEGER
                );
                CREATE TABLE epoch_enroll (
                    epoch INTEGER,
                    miner_pk TEXT,
                    weight REAL,
                    PRIMARY KEY (epoch, miner_pk)
                );
                CREATE TABLE miner_attest_recent (
                    miner TEXT PRIMARY KEY,
                    fingerprint_checks_json TEXT
                );
                CREATE TABLE balances (
                    miner_id TEXT PRIMARY KEY,
                    amount_i64 INTEGER DEFAULT 0,
                    balance_rtc REAL DEFAULT 0
                );
                """
            )
            db.execute(
                "INSERT INTO epoch_state (epoch, settled) VALUES (?, 0)",
                (7,),
            )
            db.execute(
                "INSERT INTO epoch_enroll (epoch, miner_pk, weight) VALUES (?, ?, ?)",
                (7, "miner-scale", 1.0),
            )
            db.execute(
                "INSERT INTO miner_attest_recent (miner, fingerprint_checks_json) VALUES (?, ?)",
                ("miner-scale", "{}"),
            )
            db.execute(
                "INSERT INTO balances (miner_id, amount_i64, balance_rtc) VALUES (?, 0, 0)",
                ("miner-scale",),
            )
            db.commit()

    def _stored_balance(self):
        with closing(sqlite3.connect(self.db_path)) as db:
            return db.execute(
                "SELECT amount_i64, balance_rtc FROM balances WHERE miner_id = ?",
                ("miner-scale",),
            ).fetchone()

    def _add_epoch_miner(self, miner_id, weight):
        with closing(sqlite3.connect(self.db_path)) as db:
            db.execute(
                "INSERT INTO epoch_enroll (epoch, miner_pk, weight) VALUES (?, ?, ?)",
                (7, miner_id, weight),
            )
            db.execute(
                "INSERT INTO miner_attest_recent (miner, fingerprint_checks_json) VALUES (?, ?)",
                (miner_id, "{}"),
            )
            db.execute(
                "INSERT INTO balances (miner_id, amount_i64, balance_rtc) VALUES (?, 0, 0)",
                (miner_id,),
            )
            db.commit()

    def test_finalize_epoch_writes_account_rewards_in_micro_rtc(self):
        self.mod.finalize_epoch(7, 0.01, b"")

        amount_i64, balance_rtc = self._stored_balance()
        self.assertEqual(amount_i64, 1_440_000)
        self.assertEqual(amount_i64, int(1.44 * self.mod.ACCOUNT_UNIT))
        self.assertAlmostEqual(balance_rtc, 1.44)

    def test_finalize_epoch_keeps_utxo_rewards_in_nano_rtc(self):
        calls = []

        class FakeUtxoDB:
            def __init__(self, db_path):
                self.db_path = db_path

            def apply_transaction(self, tx, height, conn=None):
                calls.append((self.db_path, tx, height, conn is not None))
                return True

        self.mod.UTXO_DUAL_WRITE = True
        self.mod.UtxoDB = FakeUtxoDB

        self.mod.finalize_epoch(7, 0.01, b"")

        amount_i64, balance_rtc = self._stored_balance()
        self.assertEqual(amount_i64, 1_440_000)
        self.assertAlmostEqual(balance_rtc, 1.44)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1]["outputs"][0]["value_nrtc"], 144_000_000)
        self.assertEqual(calls[0][1]["outputs"][0]["value_nrtc"], int(1.44 * self.mod.UTXO_UNIT))
        self.assertTrue(calls[0][3])

    def test_finalize_epoch_passes_row_connection_to_utxo_db(self):
        calls = []

        class RowCheckingUtxoDB:
            def __init__(self, db_path):
                self.db_path = db_path

            def apply_transaction(self, tx, height, conn=None):
                calls.append(conn.row_factory if conn is not None else None)
                return conn is not None and conn.row_factory is sqlite3.Row

        self.mod.UTXO_DUAL_WRITE = True
        self.mod.UtxoDB = RowCheckingUtxoDB

        self.mod.finalize_epoch(7, 0.01, b"")

        self.assertEqual(calls, [sqlite3.Row])

    def test_finalize_epoch_batches_multi_miner_utxo_rewards(self):
        self._add_epoch_miner("miner-scale-2", 1.0)
        calls = []
        seen_heights = set()

        class HeightCheckingUtxoDB:
            def __init__(self, db_path):
                self.db_path = db_path

            def apply_transaction(self, tx, height, conn=None):
                if height in seen_heights:
                    return False
                seen_heights.add(height)
                calls.append((tx, height, conn is not None))
                return True

        self.mod.UTXO_DUAL_WRITE = True
        self.mod.UtxoDB = HeightCheckingUtxoDB

        self.mod.finalize_epoch(7, 0.01, b"")

        self.assertEqual(len(calls), 1)
        tx, height, had_conn = calls[0]
        self.assertTrue(had_conn)
        self.assertEqual(height, 7 * self.mod.EPOCH_SLOTS)
        self.assertEqual(tx["tx_type"], "mining_reward")
        self.assertEqual(tx["inputs"], [])
        self.assertEqual(
            sorted(out["address"] for out in tx["outputs"]),
            ["miner-scale", "miner-scale-2"],
        )
        self.assertEqual(
            sorted(out["value_nrtc"] for out in tx["outputs"]),
            [72_000_000, 72_000_000],
        )


if __name__ == "__main__":
    unittest.main()
