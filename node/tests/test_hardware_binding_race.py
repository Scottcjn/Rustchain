# SPDX-License-Identifier: MIT
"""Regression for rustchain-bounties#16648: legacy hardware-binding race.

Two concurrent first-time submissions for the same hardware_id but different
miner ids must not both be accepted. Unpatched code returned success for the
loser after a broad `except: pass` on INSERT failure.
"""
import importlib.util
import os
import sqlite3
import sys
import tempfile
import threading
import unittest
from pathlib import Path

NODE_DIR = Path(__file__).resolve().parents[1]
MODULE_PATH = NODE_DIR / "rustchain_v2_integrated_v2.2.1_rip200.py"

DEVICE = {
    "device_model": "test-rig",
    "device_arch": "modern",
    "device_family": "x86",
    "cores": 4,
}
SIGNALS = {"macs": ["aa:bb:cc:dd:ee:ff"]}
SOURCE_IP = "203.0.113.50"


class HardwareBindingRaceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls._db = os.path.join(cls._tmp.name, "hw-binding-race.db")
        os.environ["RUSTCHAIN_DB_PATH"] = cls._db
        os.environ.setdefault("RC_ADMIN_KEY", "0123456789abcdef0123456789abcdef")
        os.environ.setdefault("RUSTCHAIN_DISABLE_P2P_AUTO_START", "1")

        if str(NODE_DIR) not in sys.path:
            sys.path.insert(0, str(NODE_DIR))

        with sqlite3.connect(cls._db) as conn:
            conn.execute(
                """CREATE TABLE hardware_bindings (
                    hardware_id TEXT PRIMARY KEY,
                    bound_miner TEXT NOT NULL,
                    device_arch TEXT,
                    device_model TEXT,
                    bound_at INTEGER NOT NULL,
                    attestation_count INTEGER DEFAULT 0
                )"""
            )

        spec = importlib.util.spec_from_file_location("rcnode_hw_binding_race", MODULE_PATH)
        cls.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.mod)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def _run_race(self):
        results = []
        lock = threading.Lock()
        start = threading.Barrier(2)

        def _check(miner_id):
            start.wait()
            res = self.mod._check_hardware_binding(
                miner_id, DEVICE, SIGNALS, source_ip=SOURCE_IP,
            )
            with lock:
                results.append(res)

        threads = [
            threading.Thread(target=_check, args=("miner-a",)),
            threading.Thread(target=_check, args=("miner-b",)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)
        return results

    def test_concurrent_first_bind_admits_only_one_miner(self):
        for _ in range(20):
            with sqlite3.connect(self._db) as conn:
                conn.execute("DELETE FROM hardware_bindings")
            results = self._run_race()
            self.assertEqual(len(results), 2, results)
            accepted = [r for r in results if r[0] is True]
            rejected = [r for r in results if r[0] is False]
            self.assertEqual(len(accepted), 1, results)
            self.assertEqual(len(rejected), 1, results)
            with sqlite3.connect(self._db) as conn:
                rows = conn.execute(
                    "SELECT bound_miner FROM hardware_bindings",
                ).fetchall()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0][0], accepted[0][2])
            self.assertEqual(rejected[0][2], accepted[0][2])

    def test_binding_check_propagates_sqlite_errors(self):
        def boom(_path, *args, **kwargs):
            raise sqlite3.OperationalError("database is locked")

        orig_connect = self.mod.sqlite3.connect
        self.mod.sqlite3.connect = boom
        try:
            with self.assertRaises(sqlite3.OperationalError):
                self.mod._check_hardware_binding(
                    "miner-a", DEVICE, SIGNALS, source_ip=SOURCE_IP,
                )
        finally:
            self.mod.sqlite3.connect = orig_connect


if __name__ == "__main__":
    unittest.main()
