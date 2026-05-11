# SPDX-License-Identifier: MIT

import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
import time
import unittest


NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULE_PATH = os.path.join(NODE_DIR, "rustchain_v2_integrated_v2.2.1_rip200.py")


class TestEpochEnrollAttestedWeight(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls._prev_db_path = os.environ.get("RUSTCHAIN_DB_PATH")
        cls._prev_admin_key = os.environ.get("RC_ADMIN_KEY")
        cls.db_path = os.path.join(cls._tmp.name, "enroll_attested_weight.db")
        os.environ["RUSTCHAIN_DB_PATH"] = cls.db_path
        os.environ["RC_ADMIN_KEY"] = "0123456789abcdef0123456789abcdef"

        if NODE_DIR not in sys.path:
            sys.path.insert(0, NODE_DIR)

        spec = importlib.util.spec_from_file_location(
            "rustchain_epoch_enroll_attested_weight_test",
            MODULE_PATH,
        )
        cls.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.mod)

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
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(
                """
                DROP TABLE IF EXISTS miner_attest_recent;
                DROP TABLE IF EXISTS miner_macs;
                DROP TABLE IF EXISTS epoch_enroll;
                DROP TABLE IF EXISTS balances;
                DROP TABLE IF EXISTS miner_header_keys;
                DROP TABLE IF EXISTS epoch_fingerprint_rotation;

                CREATE TABLE miner_attest_recent (
                    miner TEXT PRIMARY KEY,
                    ts_ok INTEGER NOT NULL,
                    device_family TEXT,
                    device_arch TEXT,
                    entropy_score REAL DEFAULT 0,
                    fingerprint_passed INTEGER DEFAULT 0,
                    source_ip TEXT,
                    fingerprint_checks_json TEXT
                );
                CREATE TABLE miner_macs (
                    miner TEXT NOT NULL,
                    mac_hash TEXT NOT NULL,
                    first_ts INTEGER NOT NULL,
                    last_ts INTEGER NOT NULL,
                    count INTEGER NOT NULL DEFAULT 1,
                    PRIMARY KEY (miner, mac_hash)
                );
                CREATE TABLE epoch_enroll (
                    epoch INTEGER,
                    miner_pk TEXT,
                    weight INTEGER,
                    PRIMARY KEY (epoch, miner_pk)
                );
                CREATE TABLE balances (
                    miner_pk TEXT PRIMARY KEY,
                    balance_rtc REAL NOT NULL DEFAULT 0
                );
                CREATE TABLE miner_header_keys (
                    miner_id TEXT PRIMARY KEY,
                    pubkey_hex TEXT NOT NULL
                );
                """
            )

    def _enroll(self, payload):
        with self.mod.app.test_request_context("/epoch/enroll", method="POST", json=payload):
            resp = self.mod.enroll_epoch()
        if isinstance(resp, tuple):
            body, status = resp
            return status, body.get_json()
        return resp.status_code, resp.get_json()

    def test_enrollment_uses_attested_device_and_fingerprint_not_request_payload(self):
        miner = "RTC_WEIGHT_SPOOF_MINER"
        now = int(time.time())
        attested_checks = {
            "clock_drift": True,
            "cache_timing": True,
            "simd_bias": True,
            "thermal_drift": True,
            "instruction_jitter": True,
            "anti_emulation": True,
        }
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO miner_attest_recent
                    (miner, ts_ok, device_family, device_arch, fingerprint_passed,
                     source_ip, fingerprint_checks_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    miner,
                    now,
                    "x86_64",
                    "default",
                    1,
                    "127.0.0.1",
                    json.dumps(attested_checks),
                ),
            )
            conn.execute(
                """
                INSERT INTO miner_macs
                    (miner, mac_hash, first_ts, last_ts, count)
                VALUES (?, ?, ?, ?, ?)
                """,
                (miner, "mac-hash", now, now, 1),
            )

        request_controlled_checks = {
            name: {"passed": True, "data": {"request_controlled": True}}
            for name in attested_checks
        }
        status, body = self._enroll(
            {
                "miner_pubkey": miner,
                "miner_id": miner,
                "device": {"family": "PowerPC", "arch": "G4"},
                "fingerprint": {"checks": request_controlled_checks},
            }
        )

        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])
        self.assertEqual(body["hw_weight"], 0.8)
        self.assertEqual(body["weight"], 0.8)

        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT weight FROM epoch_enroll WHERE epoch = ? AND miner_pk = ?",
                (body["epoch"], miner),
            ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(int(row[0]), self.mod.epoch_weight_to_units(0.8))


if __name__ == "__main__":
    unittest.main()
