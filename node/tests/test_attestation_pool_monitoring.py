# SPDX-License-Identifier: MIT
import importlib.util
import os
import sqlite3
import sys
import tempfile
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


class TestAttestationPoolMonitoring(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls._prev_db_path = os.environ.get("RUSTCHAIN_DB_PATH")
        cls._prev_admin_key = os.environ.get("RC_ADMIN_KEY")
        os.environ["RUSTCHAIN_DB_PATH"] = os.path.join(cls._tmp.name, "attestation-pool.db")
        os.environ["RC_ADMIN_KEY"] = "0123456789abcdef0123456789abcdef"

        if NODE_DIR not in sys.path:
            sys.path.insert(0, NODE_DIR)

        prometheus_client = None
        prev_metrics = None
        try:
            import prometheus_client

            prev_metrics = (
                prometheus_client.Counter,
                prometheus_client.Gauge,
                prometheus_client.Histogram,
            )
            prometheus_client.Counter = _NoopMetric
            prometheus_client.Gauge = _NoopMetric
            prometheus_client.Histogram = _NoopMetric
        except ModuleNotFoundError:
            pass

        spec = importlib.util.spec_from_file_location(
            "rustchain_attestation_pool_monitoring_test",
            MODULE_PATH,
        )
        cls.mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(cls.mod)
        finally:
            if prometheus_client is not None and prev_metrics is not None:
                (
                    prometheus_client.Counter,
                    prometheus_client.Gauge,
                    prometheus_client.Histogram,
                ) = prev_metrics
        cls.client = cls.mod.app.test_client()

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
        cls._tmp.cleanup()

    def setUp(self):
        with sqlite3.connect(self.mod.DB_PATH) as conn:
            conn.execute("DROP TABLE IF EXISTS miner_attest_recent")
            conn.execute("DROP TABLE IF EXISTS miner_attest_history")

    def test_attestation_pool_endpoint_handles_missing_tables(self):
        resp = self.client.get("/api/attestation-pool")

        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertTrue(body["ok"])
        self.assertFalse(body["tables"]["miner_attest_recent"])
        self.assertEqual(body["pool"]["active_miners"], 0)
        self.assertEqual(body["history"], [])

    def test_attestation_pool_reports_current_and_history_counts(self):
        now = 1_800_000_000
        with sqlite3.connect(self.mod.DB_PATH) as conn:
            conn.execute(
                """
                CREATE TABLE miner_attest_recent (
                    miner TEXT PRIMARY KEY,
                    ts_ok INTEGER,
                    device_family TEXT,
                    device_arch TEXT,
                    entropy_score REAL,
                    fingerprint_passed INTEGER
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE miner_attest_history (
                    miner TEXT,
                    ts_ok INTEGER,
                    device_family TEXT,
                    device_arch TEXT,
                    entropy_score REAL,
                    fingerprint_passed INTEGER
                )
                """
            )
            conn.executemany(
                """
                INSERT INTO miner_attest_recent
                    (miner, ts_ok, device_family, device_arch, entropy_score, fingerprint_passed)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    ("alice", now - 60, "x86", "x86_64", 0.91, 1),
                    ("bob", now - 90, "apple", "m2", 0.73, 0),
                    ("carol", now - 7200, "ppc", "g4", 0.52, 1),
                ],
            )
            conn.executemany(
                """
                INSERT INTO miner_attest_history
                    (miner, ts_ok, device_family, device_arch, entropy_score, fingerprint_passed)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    ("alice", now - 60, "x86", "x86_64", 0.91, 1),
                    ("alice", now - 3700, "x86", "x86_64", 0.88, 1),
                    ("bob", now - 90, "apple", "m2", 0.73, 0),
                    ("old", now - 90_000, "x86", "x86_64", 0.1, 0),
                ],
            )

        snap = self.mod._attestation_pool_snapshot(now_ts=now)

        self.assertEqual(snap["pool"]["known_miners"], 3)
        self.assertEqual(snap["pool"]["active_miners"], 2)
        self.assertEqual(snap["pool"]["stale_miners"], 1)
        self.assertEqual(snap["pool"]["fingerprint_passed_active"], 1)
        self.assertEqual(snap["pool"]["recent_attestations_24h"], 3)
        self.assertEqual(
            snap["by_device_arch"],
            [
                {"device_arch": "m2", "active_miners": 1},
                {"device_arch": "x86_64", "active_miners": 1},
            ],
        )

    def test_attestation_history_schema_has_timestamp_index(self):
        self.mod.init_db()

        with sqlite3.connect(self.mod.DB_PATH) as conn:
            indexes = {
                row[1]: [
                    col[2]
                    for col in conn.execute(f"PRAGMA index_info({row[1]})").fetchall()
                ]
                for row in conn.execute("PRAGMA index_list(miner_attest_history)").fetchall()
            }

        self.assertEqual(indexes["idx_attest_history_ts_only"], ["ts_ok"])

    def test_prometheus_metrics_include_attestation_pool_lines(self):
        now = 1_800_000_000
        with sqlite3.connect(self.mod.DB_PATH) as conn:
            conn.execute(
                """
                CREATE TABLE miner_attest_recent (
                    miner TEXT PRIMARY KEY,
                    ts_ok INTEGER,
                    device_arch TEXT,
                    entropy_score REAL,
                    fingerprint_passed INTEGER
                )
                """
            )
            conn.execute(
                "INSERT INTO miner_attest_recent VALUES (?, ?, ?, ?, ?)",
                ("alice", now - 10, 'riscv"dev\\gpu\nrack', 0.5, 1),
            )

        text = self.mod._attestation_pool_prometheus_text(now_ts=now)

        self.assertIn("rustchain_attestation_pool_active_miners 1", text)
        self.assertIn("rustchain_attestation_pool_stale_miners 0", text)
        self.assertIn('device_arch="riscv\\"dev\\\\gpu\\nrack"', text)
        self.assertIn("rustchain_attestation_pool_scrape_ok 1", text)


if __name__ == "__main__":
    unittest.main()
