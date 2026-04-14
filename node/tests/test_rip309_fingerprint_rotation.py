#!/usr/bin/env python3
import os
import sqlite3
import sys
import tempfile
import unittest
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NODE_DIR = ROOT / "node"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(NODE_DIR))

os.environ.setdefault("RC_ADMIN_KEY", "0" * 32)
os.environ.setdefault("DB_PATH", ":memory:")


def _load_module(module_name: str, file_name: str, aliases=()):
    for alias in aliases:
        if alias in sys.modules:
            return sys.modules[alias]
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, str(NODE_DIR / file_name))
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


rr_mod = _load_module("rr_mod_issue3008", "rip_200_round_robin_1cpu1vote.py", aliases=("rr_mod",))
integrated_node = _load_module("integrated_node_issue3008", "rustchain_v2_integrated_v2.2.1_rip200.py", aliases=("integrated_node",))


class TestRIP309FingerprintRotation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.tmp.name
        self.tmp.close()
        self.conn = sqlite3.connect(self.db_path)
        self.conn.executescript(
            """
            CREATE TABLE epoch_enroll (
                epoch INTEGER,
                miner_pk TEXT,
                weight REAL,
                PRIMARY KEY (epoch, miner_pk)
            );
            CREATE TABLE miner_attest_recent (
                miner TEXT PRIMARY KEY,
                device_arch TEXT,
                fingerprint_passed INTEGER DEFAULT 1,
                entropy_score REAL DEFAULT 0,
                ts_ok INTEGER,
                warthog_bonus REAL DEFAULT 1.0
            );
            CREATE TABLE blocks (
                height INTEGER PRIMARY KEY,
                block_hash TEXT NOT NULL
            );
            """
        )
        integrated_node.ensure_epoch_fingerprint_rotation_table(self.conn)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        os.unlink(self.db_path)

    def test_rotation_differs_across_epochs(self):
        self.conn.execute("INSERT INTO blocks (height, block_hash) VALUES (?, ?)", (143, "a" * 64))
        self.conn.execute("INSERT INTO blocks (height, block_hash) VALUES (?, ?)", (287, "b" * 64))
        self.conn.commit()

        epoch1 = integrated_node.get_epoch_fingerprint_rotation(self.conn, 1)
        epoch2 = integrated_node.get_epoch_fingerprint_rotation(self.conn, 2)

        self.assertEqual(len(epoch1["active_checks"]), 4)
        self.assertEqual(len(epoch2["active_checks"]), 4)
        self.assertNotEqual(epoch1["measurement_nonce"], epoch2["measurement_nonce"])
        self.assertNotEqual(epoch1["active_checks"], epoch2["active_checks"])

    def test_reward_calc_uses_epoch_snapshot_weight(self):
        epoch = 3
        current_slot = epoch * integrated_node.EPOCH_SLOTS + 5
        self.conn.execute("INSERT INTO epoch_enroll (epoch, miner_pk, weight) VALUES (?, ?, ?)", (epoch, "rotated", 0.5))
        self.conn.execute("INSERT INTO epoch_enroll (epoch, miner_pk, weight) VALUES (?, ?, ?)", (epoch, "full", 1.0))
        self.conn.execute(
            "INSERT INTO miner_attest_recent (miner, device_arch, fingerprint_passed, ts_ok) VALUES (?, ?, ?, ?)",
            ("rotated", "g4", 1, integrated_node.GENESIS_TIMESTAMP),
        )
        self.conn.execute(
            "INSERT INTO miner_attest_recent (miner, device_arch, fingerprint_passed, ts_ok) VALUES (?, ?, ?, ?)",
            ("full", "g4", 1, integrated_node.GENESIS_TIMESTAMP),
        )
        self.conn.commit()

        rewards = rr_mod.calculate_epoch_rewards_time_aged(
            self.db_path,
            epoch,
            int(1.5 * 1_000_000),
            current_slot,
        )

        self.assertEqual(sum(rewards.values()), int(1.5 * 1_000_000))
        self.assertGreater(rewards["full"], rewards["rotated"])
        ratio = rewards["full"] / rewards["rotated"]
        self.assertGreater(ratio, 1.9)
        self.assertLess(ratio, 2.1)

    def test_rotation_eval_counts_only_active_checks(self):
        self.conn.execute("INSERT INTO blocks (height, block_hash) VALUES (?, ?)", (143, "c" * 64))
        self.conn.commit()
        rotation = integrated_node.get_epoch_fingerprint_rotation(self.conn, 1)

        fingerprint = {"checks": {name: {"passed": True, "data": {"ok": True}} for name in integrated_node.RIP309_ROTATING_FINGERPRINT_CHECKS}}
        inactive = next(name for name in integrated_node.RIP309_ROTATING_FINGERPRINT_CHECKS if name not in rotation["active_checks"])
        fingerprint["checks"][inactive] = {"passed": False, "data": {"ok": False}}

        result = integrated_node.evaluate_rotating_fingerprint_checks(self.conn, 1, fingerprint)
        self.assertEqual(result["active_pass_count"], 4)
        self.assertEqual(result["active_total"], 4)
        self.assertEqual(result["failed_active_checks"], [])
        self.assertEqual(result["active_ratio"], 1.0)


if __name__ == "__main__":
    unittest.main()
