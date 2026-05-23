# SPDX-License-Identifier: MIT

import importlib.util
import gc
import os
import sqlite3
import sys
import tempfile
import time
import unittest
from contextlib import closing
from pathlib import Path


NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULE_PATH = os.path.join(NODE_DIR, "rustchain_v2_integrated_v2.2.1_rip200.py")

EXTRA_SCHEMA = [
    "CREATE TABLE IF NOT EXISTS blocked_wallets (wallet TEXT PRIMARY KEY, reason TEXT)",
    "CREATE TABLE IF NOT EXISTS ip_rate_limit (client_ip TEXT NOT NULL, miner_id TEXT NOT NULL, ts INTEGER NOT NULL, PRIMARY KEY (client_ip, miner_id))",
    "CREATE TABLE IF NOT EXISTS miner_attest_recent (miner TEXT PRIMARY KEY, ts_ok INTEGER NOT NULL, device_family TEXT, device_arch TEXT, entropy_score REAL DEFAULT 0, fingerprint_passed INTEGER DEFAULT 0, source_ip TEXT, warthog_bonus REAL DEFAULT 1.0)",
    "CREATE TABLE IF NOT EXISTS hardware_bindings (hardware_id TEXT PRIMARY KEY, bound_miner TEXT NOT NULL, device_arch TEXT, device_model TEXT, bound_at INTEGER NOT NULL, attestation_count INTEGER DEFAULT 0)",
    "CREATE TABLE IF NOT EXISTS miner_header_keys (miner_id TEXT PRIMARY KEY, pubkey_hex TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS miner_macs (miner TEXT NOT NULL, mac_hash TEXT NOT NULL, first_ts INTEGER NOT NULL, last_ts INTEGER NOT NULL, count INTEGER NOT NULL DEFAULT 1, PRIMARY KEY (miner, mac_hash))",
]


class TestAttestSubmitChallengeBinding(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls._prev_admin_key = os.environ.get("RC_ADMIN_KEY")
        cls._prev_db_path = os.environ.get("RUSTCHAIN_DB_PATH")
        cls._prev_disable_p2p = os.environ.get("RUSTCHAIN_DISABLE_P2P_AUTO_START")
        cls._loaded_modules = []
        gc.collect()
        os.environ["RC_ADMIN_KEY"] = "0123456789abcdef0123456789abcdef"
        os.environ["RUSTCHAIN_DISABLE_P2P_AUTO_START"] = "1"

        if NODE_DIR not in sys.path:
            sys.path.insert(0, NODE_DIR)

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
        if cls._prev_disable_p2p is None:
            os.environ.pop("RUSTCHAIN_DISABLE_P2P_AUTO_START", None)
        else:
            os.environ["RUSTCHAIN_DISABLE_P2P_AUTO_START"] = cls._prev_disable_p2p
        cls._release_loaded_modules()
        for attempt in range(5):
            try:
                cls._tmp.cleanup()
                break
            except PermissionError:
                if attempt == 4:
                    raise
                gc.collect()
                time.sleep(0.2)

    @classmethod
    def _release_loaded_modules(cls):
        try:
            from prometheus_client import REGISTRY
        except Exception:
            cls._loaded_modules = []
            return

        for mod in cls._loaded_modules:
            block_sync = getattr(mod, "block_sync", None)
            if block_sync is not None:
                stop = getattr(block_sync, "stop", None)
                if callable(stop):
                    stop()
                else:
                    block_sync.running = False

            for metric_name in (
                "withdrawal_requests",
                "withdrawal_completed",
                "withdrawal_failed",
                "balance_gauge",
                "epoch_gauge",
                "withdrawal_queue_size",
            ):
                metric = getattr(mod, metric_name, None)
                if metric is None:
                    continue
                try:
                    REGISTRY.unregister(metric)
                except (KeyError, ValueError):
                    pass
        cls._loaded_modules = []

    def tearDown(self):
        self._release_loaded_modules()

    def _db_path(self, name: str) -> str:
        return str(Path(self._tmp.name) / name)

    def _load_module(self, module_name: str, db_name: str):
        self._release_loaded_modules()
        db_path = self._db_path(db_name)
        os.environ["RUSTCHAIN_DB_PATH"] = db_path
        spec = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self._loaded_modules.append(mod)
        mod.HAVE_REPLAY_DEFENSE = False
        mod.HAVE_WARTHOG = False
        for attempt in range(5):
            try:
                mod.init_db()
                break
            except sqlite3.OperationalError as exc:
                if "locked" not in str(exc).lower() or attempt == 4:
                    raise
                time.sleep(0.2)
        with closing(sqlite3.connect(db_path)) as conn:
            for stmt in EXTRA_SCHEMA:
                conn.execute(stmt)
            conn.commit()
        return mod, db_path

    def _response_payload(self, resp):
        if isinstance(resp, tuple):
            body, status = resp
            return status, body.get_json()
        return resp.status_code, resp.get_json()

    def _submit(self, mod, payload):
        with mod.app.test_request_context("/attest/submit", method="POST", json=payload):
            return self._response_payload(mod._submit_attestation_impl())

    def _fingerprint(self):
        return {
            "checks": {
                "anti_emulation": {"passed": True, "data": {"vm_indicators": []}},
                "clock_drift": {"passed": True, "data": {"cv": 0.05, "samples": 64}},
            },
            "all_passed": True,
        }

    def _attestation_payload(self, nonce):
        return {
            "miner": "RTC_REPLAY_POC_MINER",
            "report": {"nonce": nonce, "commitment": "deadbeef"},
            "device": {"family": "x86_64", "arch": "default", "model": "poc-box", "cores": 4},
            "signals": {"hostname": "poc-host", "macs": []},
            "fingerprint": self._fingerprint(),
        }

    def test_same_challenge_nonce_rejected_on_different_node(self):
        mod1, db1_path = self._load_module("rustchain_attest_node1", "node1.db")
        mod2, db2_path = self._load_module("rustchain_attest_node2", "node2.db")

        with mod1.app.test_request_context("/attest/challenge", method="POST", json={}):
            challenge_resp = mod1.get_challenge()
        challenge = challenge_resp.get_json()

        payload = self._attestation_payload(challenge["nonce"])

        status1, body1 = self._submit(mod1, payload)
        status2, body2 = self._submit(mod2, payload)

        self.assertEqual(status1, 200)
        self.assertTrue(body1["ok"])
        self.assertEqual(status2, 409)
        self.assertEqual(body2["code"], "CHALLENGE_INVALID")

        with closing(sqlite3.connect(db1_path)) as conn1, closing(sqlite3.connect(db2_path)) as conn2:
            self.assertEqual(conn1.execute("SELECT COUNT(*) FROM used_nonces").fetchone()[0], 1)
            self.assertEqual(conn2.execute("SELECT COUNT(*) FROM nonces").fetchone()[0], 0)
            self.assertEqual(conn2.execute("SELECT COUNT(*) FROM used_nonces").fetchone()[0], 0)

    def test_same_challenge_nonce_rejected_on_same_node_replay(self):
        mod, db_path = self._load_module("rustchain_attest_node_single", "single.db")

        with mod.app.test_request_context("/attest/challenge", method="POST", json={}):
            challenge_resp = mod.get_challenge()
        challenge = challenge_resp.get_json()

        payload = self._attestation_payload(challenge["nonce"])

        status1, body1 = self._submit(mod, payload)
        status2, body2 = self._submit(mod, payload)

        self.assertEqual(status1, 200)
        self.assertTrue(body1["ok"])
        self.assertEqual(status2, 409)
        self.assertEqual(body2["code"], "NONCE_REPLAY")

        with closing(sqlite3.connect(db_path)) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM used_nonces").fetchone()[0], 1)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM nonces").fetchone()[0], 0)

    def test_client_timestamp_cannot_bypass_challenge_validation(self):
        mod, db_path = self._load_module("rustchain_attest_node_bypass", "bypass.db")

        payload = self._attestation_payload("b" * 64)
        payload["report"]["server_time"] = 1700000000

        status, body = self._submit(mod, payload)

        self.assertEqual(status, 409)
        self.assertEqual(body["code"], "CHALLENGE_INVALID")

        with closing(sqlite3.connect(db_path)) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM nonces").fetchone()[0], 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM used_nonces").fetchone()[0], 0)

    def test_submit_rejects_arbitrary_nonce_without_server_challenge(self):
        mod, db_path = self._load_module("rustchain_attest_node_plain", "plain.db")

        payload = self._attestation_payload("legacy-local-nonce")

        status, body = self._submit(mod, payload)

        self.assertEqual(status, 409)
        self.assertEqual(body["code"], "CHALLENGE_INVALID")

        with closing(sqlite3.connect(db_path)) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM nonces").fetchone()[0], 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM used_nonces").fetchone()[0], 0)

    def test_missing_required_attestation_evidence_does_not_consume_nonce(self):
        mod, db_path = self._load_module("rustchain_attest_required_evidence", "required_evidence.db")

        cases = [
            ("device", "MISSING_DEVICE"),
            ("signals", "MISSING_SIGNALS"),
            ("fingerprint", "MISSING_FINGERPRINT"),
        ]
        for missing_field, expected_code in cases:
            with self.subTest(missing_field=missing_field):
                with mod.app.test_request_context("/attest/challenge", method="POST", json={}):
                    challenge_resp = mod.get_challenge()
                challenge = challenge_resp.get_json()
                payload = self._attestation_payload(challenge["nonce"])
                payload.pop(missing_field)

                status, body = self._submit(mod, payload)

                self.assertEqual(status, 422)
                self.assertEqual(body["code"], expected_code)
                with sqlite3.connect(db_path) as conn:
                    self.assertEqual(
                        conn.execute("SELECT COUNT(*) FROM nonces WHERE nonce = ?", (challenge["nonce"],)).fetchone()[0],
                        1,
                    )
                    self.assertEqual(
                        conn.execute("SELECT COUNT(*) FROM used_nonces WHERE nonce = ?", (challenge["nonce"],)).fetchone()[0],
                        0,
                    )

    def test_non_string_signature_does_not_consume_nonce(self):
        mod, db_path = self._load_module("rustchain_attest_signature_type", "signature_type.db")

        with mod.app.test_request_context("/attest/challenge", method="POST", json={}):
            challenge_resp = mod.get_challenge()
        challenge = challenge_resp.get_json()
        payload = self._attestation_payload(challenge["nonce"])
        payload["signature"] = True

        status, body = self._submit(mod, payload)

        self.assertEqual(status, 400)
        self.assertEqual(body["code"], "INVALID_SIGNATURE_TYPE")
        with sqlite3.connect(db_path) as conn:
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM nonces WHERE nonce = ?", (challenge["nonce"],)).fetchone()[0],
                1,
            )
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM used_nonces WHERE nonce = ?", (challenge["nonce"],)).fetchone()[0],
                0,
            )


if __name__ == "__main__":
    unittest.main()
