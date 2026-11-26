"""
Unit tests for RustChain Attestation & Reward Data Export Pipeline (Bounty #49)
"""

import json
import os
import sqlite3
import tempfile
import unittest
from tools.rustchain_export import export_db_mode, run_pipeline, filter_by_date


class TestRustChainExport(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.test_dir.name, "test_rustchain.db")
        self.output_dir = os.path.join(self.test_dir.name, "output")

        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        # Create mock tables
        cur.execute("""
            CREATE TABLE miner_attest_recent (
                miner_id TEXT PRIMARY KEY,
                arch TEXT,
                last_seen TEXT,
                earnings REAL
            )
        """)
        cur.execute("INSERT INTO miner_attest_recent VALUES ('RTCtest1', 'ppc_g4', '2026-02-15T12:00:00Z', 150.5)")
        cur.execute("INSERT INTO miner_attest_recent VALUES ('RTCtest2', 'x86_64', '2026-02-16T14:00:00Z', 45.0)")

        cur.execute("""
            CREATE TABLE epoch_state (
                epoch INTEGER PRIMARY KEY,
                timestamp TEXT,
                pot_size REAL,
                status TEXT
            )
        """)
        cur.execute("INSERT INTO epoch_state VALUES (101, '2026-02-15T00:00:00Z', 500.0, 'settled')")
        cur.execute("INSERT INTO epoch_state VALUES (102, '2026-02-16T00:00:00Z', 550.0, 'settled')")

        cur.execute("""
            CREATE TABLE epoch_rewards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                epoch INTEGER,
                miner_id TEXT,
                amount REAL,
                timestamp TEXT
            )
        """)
        cur.execute("INSERT INTO epoch_rewards (epoch, miner_id, amount, timestamp) VALUES (101, 'RTCtest1', 100.0, '2026-02-15T01:00:00Z')")
        cur.execute("INSERT INTO epoch_rewards (epoch, miner_id, amount, timestamp) VALUES (102, 'RTCtest2', 45.0, '2026-02-16T01:00:00Z')")

        cur.execute("""
            CREATE TABLE ledger (
                tx_hash TEXT PRIMARY KEY,
                sender TEXT,
                recipient TEXT,
                amount REAL,
                timestamp TEXT
            )
        """)
        cur.execute("INSERT INTO ledger VALUES ('0xabc', 'treasury', 'RTCtest1', 100.0, '2026-02-15T01:00:00Z')")

        cur.execute("""
            CREATE TABLE balances (
                miner_id TEXT PRIMARY KEY,
                balance REAL
            )
        """)
        cur.execute("INSERT INTO balances VALUES ('RTCtest1', 250.5)")
        cur.execute("INSERT INTO balances VALUES ('RTCtest2', 45.0)")

        conn.commit()
        conn.close()

    def tearDown(self):
        self.test_dir.cleanup()

    def test_db_mode_export(self):
        data = export_db_mode(self.db_path, None, None)
        self.assertEqual(len(data["miners"]), 2)
        self.assertEqual(len(data["epochs"]), 2)
        self.assertEqual(len(data["rewards"]), 2)
        self.assertEqual(len(data["attestations"]), 1)
        self.assertEqual(len(data["balances"]), 2)

    def test_date_filtering(self):
        data = export_db_mode(self.db_path, from_date="2026-02-16T00:00:00Z", to_date="2026-02-16T23:59:59Z")
        self.assertEqual(len(data["epochs"]), 1)
        self.assertEqual(data["epochs"][0]["epoch"], 102)

    def test_run_pipeline_csv_and_json(self):
        # Test CSV run
        summary_csv = run_pipeline(
            mode="db",
            target=self.db_path,
            output_dir=self.output_dir,
            export_format="csv"
        )
        self.assertTrue(os.path.exists(os.path.join(self.output_dir, "miners.csv")))
        self.assertTrue(os.path.exists(os.path.join(self.output_dir, "export_manifest.json")))
        self.assertEqual(summary_csv["miners"], 2)

        # Test JSON run
        summary_json = run_pipeline(
            mode="db",
            target=self.db_path,
            output_dir=self.output_dir,
            export_format="json"
        )
        self.assertTrue(os.path.exists(os.path.join(self.output_dir, "epochs.json")))
        with open(os.path.join(self.output_dir, "epochs.json"), "r") as f:
            epochs_data = json.load(f)
            self.assertEqual(len(epochs_data), 2)


if __name__ == "__main__":
    unittest.main()
