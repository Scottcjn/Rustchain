# SPDX-License-Identifier: MIT
import importlib.util
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

NODE_DIR = Path(__file__).resolve().parents[1]
MODULE_PATH = NODE_DIR / "rustchain_v2_integrated_v2.2.1_rip200.py"

HEADER_SCHEMA = """
CREATE TABLE IF NOT EXISTS headers(
    slot INTEGER PRIMARY KEY,
    miner_id TEXT,
    message_hex TEXT,
    signature_hex TEXT,
    pubkey_hex TEXT,
    header_json TEXT
)
"""

EPOCH_ENROLL_SCHEMA = """
CREATE TABLE IF NOT EXISTS epoch_enroll(
    epoch INTEGER,
    miner_pk TEXT,
    weight REAL,
    PRIMARY KEY (epoch, miner_pk)
)
"""


class TestContinuityAuditPhase2(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls._prev_admin_key = os.environ.get("RC_ADMIN_KEY")
        cls._prev_db_path = os.environ.get("RUSTCHAIN_DB_PATH")
        cls._db_path = str(Path(cls._tmp.name) / "rip309_phase2.db")
        os.environ["RC_ADMIN_KEY"] = "0" * 32
        os.environ["RUSTCHAIN_DB_PATH"] = cls._db_path

        if "integrated_node" in sys.modules:
            cls.mod = sys.modules["integrated_node"]
            cls.mod.DB_PATH = cls._db_path
        else:
            spec = importlib.util.spec_from_file_location("rustchain_rip309_phase2", MODULE_PATH)
            cls.mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cls.mod)
            cls.mod.DB_PATH = cls._db_path

    @classmethod
    def tearDownClass(cls):
        if cls._prev_admin_key is None:
            os.environ.pop("RC_ADMIN_KEY", None)
        else:
            os.environ["RC_ADMIN_KEY"] = cls._prev_admin_key
        if cls._prev_db_path is None:
            os.environ.pop("RUSTCHAIN_DB_PATH", None)
        else:
            os.environ["RUSTCHAIN_DB_PATH"] = cls._prev_db_path
        cls._tmp.cleanup()

    def setUp(self):
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("DROP TABLE IF EXISTS headers")
            conn.execute("DROP TABLE IF EXISTS epoch_enroll")
            conn.execute(HEADER_SCHEMA)
            conn.execute(EPOCH_ENROLL_SCHEMA)
            conn.commit()

    def test_nonce_and_window_are_deterministic_and_in_range(self):
        mod = self.mod
        prev_digest = mod.hashlib.sha256(b"epoch-42-terminal-header").hexdigest()

        nonce_a = mod.derive_epoch_nonce(prev_digest)
        nonce_b = mod.derive_epoch_nonce(prev_digest)
        self.assertEqual(nonce_a, nonce_b)

        hours = mod.get_observation_window_hours(nonce_a)
        self.assertGreaterEqual(hours, 6)
        self.assertLessEqual(hours, 168)

    def test_window_uses_previous_epoch_terminal_header(self):
        mod = self.mod
        db_path = self._db_path
        prev_epoch = 4
        terminal_slot = (prev_epoch + 1) * mod.EPOCH_SLOTS - 1
        current_epoch = prev_epoch + 1
        epoch_start_ts = mod.GENESIS_TIMESTAMP + (current_epoch * mod.EPOCH_SLOTS * mod.BLOCK_TIME)

        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "INSERT INTO headers(slot, miner_id, message_hex, signature_hex, pubkey_hex, header_json) VALUES (?, ?, ?, ?, ?, ?)",
                (terminal_slot, "miner-a", "aa11", "bb22", "cc33", '{"slot": 719}')
            )
            conn.execute(
                "INSERT INTO headers(slot, miner_id, message_hex, signature_hex, pubkey_hex, header_json) VALUES (?, ?, ?, ?, ?, ?)",
                (terminal_slot - 1, "miner-b", "older", "sig", "pk", '{"slot": 718}')
            )
            conn.commit()
            audit = mod.get_continuity_audit_window(conn, current_epoch, epoch_start_ts)

        self.assertEqual(audit["previous_epoch_terminal_slot"], terminal_slot)
        self.assertEqual(audit["digest_source"], "terminal_header")
        self.assertEqual(audit["window_starts_at"], epoch_start_ts)
        self.assertEqual(audit["window_ends_at"], epoch_start_ts + audit["window_seconds"])
        self.assertGreaterEqual(audit["window_hours"], 6)
        self.assertLessEqual(audit["window_hours"], 168)

    def test_epoch_endpoint_exposes_live_continuity_audit_payload(self):
        mod = self.mod
        db_path = self._db_path
        slot = 5 * mod.EPOCH_SLOTS
        epoch = 5
        previous_terminal_slot = slot - 1

        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "INSERT INTO headers(slot, miner_id, message_hex, signature_hex, pubkey_hex, header_json) VALUES (?, ?, ?, ?, ?, ?)",
                (previous_terminal_slot, "miner-live", "abc", "def", "ghi", '{"slot": 719}')
            )
            conn.execute(
                "INSERT INTO epoch_enroll(epoch, miner_pk, weight) VALUES (?, ?, ?)",
                (epoch, "RTC_TEST_MINER", 1.0)
            )
            conn.commit()

        original_current_slot = mod.current_slot
        try:
            mod.current_slot = lambda: slot
            with mod.app.test_request_context("/epoch", method="GET"):
                payload = mod.get_epoch().get_json()
        finally:
            mod.current_slot = original_current_slot

        audit = payload["continuity_audit"]
        self.assertEqual(payload["epoch"], epoch)
        self.assertEqual(payload["enrolled_miners"], 1)
        self.assertEqual(audit["previous_epoch_terminal_slot"], previous_terminal_slot)
        self.assertEqual(audit["window_anchor"], "epoch_start")
        self.assertEqual(audit["digest_source"], "terminal_header")
        self.assertGreaterEqual(audit["window_hours"], 6)
        self.assertLessEqual(audit["window_hours"], 168)
        self.assertEqual(audit["window_seconds"], audit["window_hours"] * 3600)


if __name__ == "__main__":
    unittest.main()
