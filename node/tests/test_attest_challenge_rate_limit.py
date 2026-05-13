# SPDX-License-Identifier: MIT
import importlib.util
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULE_PATH = os.path.join(NODE_DIR, "rustchain_v2_integrated_v2.2.1_rip200.py")


class TestAttestChallengeRateLimit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls._prev_admin_key = os.environ.get("RC_ADMIN_KEY")
        cls._prev_db_path = os.environ.get("RUSTCHAIN_DB_PATH")
        os.environ["RC_ADMIN_KEY"] = "0123456789abcdef0123456789abcdef"

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
        cls._tmp.cleanup()

    def _load_module(self, module_name: str, db_name: str):
        db_path = str(Path(self._tmp.name) / db_name)
        os.environ["RUSTCHAIN_DB_PATH"] = db_path
        spec = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        with sqlite3.connect(db_path) as conn:
            mod.attest_ensure_tables(conn)
        mod.ATTEST_CHALLENGE_IP_LIMIT = 2
        mod.ATTEST_CHALLENGE_IP_WINDOW = 60
        return mod, db_path

    def _response_payload(self, resp):
        if isinstance(resp, tuple):
            body, status = resp
            return status, body.get_json()
        return resp.status_code, resp.get_json()

    def test_challenge_endpoint_limits_repeated_requests_per_ip(self):
        mod, db_path = self._load_module("rustchain_challenge_limit", "challenge_limit.db")

        statuses = []
        for _ in range(3):
            with mod.app.test_request_context(
                "/attest/challenge",
                method="POST",
                json={},
                environ_base={"REMOTE_ADDR": "203.0.113.10"},
            ), mock.patch.object(mod.time, "time", return_value=1000):
                statuses.append(self._response_payload(mod.get_challenge()))

        self.assertEqual(statuses[0][0], 200)
        self.assertEqual(statuses[1][0], 200)
        self.assertEqual(statuses[2][0], 429)
        self.assertEqual(statuses[2][1]["code"], "CHALLENGE_RATE_LIMIT")

        with sqlite3.connect(db_path) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM nonces").fetchone()[0], 2)
            self.assertEqual(
                conn.execute(
                    "SELECT request_count FROM attest_challenge_rate_limit WHERE client_ip = ?",
                    ("203.0.113.10",),
                ).fetchone()[0],
                3,
            )

    def test_challenge_rate_limit_window_resets(self):
        mod, db_path = self._load_module("rustchain_challenge_window", "challenge_window.db")

        for _ in range(2):
            with mod.app.test_request_context(
                "/attest/challenge",
                method="POST",
                json={},
                environ_base={"REMOTE_ADDR": "203.0.113.11"},
            ), mock.patch.object(mod.time, "time", return_value=1000):
                status, _ = self._response_payload(mod.get_challenge())
                self.assertEqual(status, 200)

        with mod.app.test_request_context(
            "/attest/challenge",
            method="POST",
            json={},
            environ_base={"REMOTE_ADDR": "203.0.113.11"},
        ), mock.patch.object(mod.time, "time", return_value=1061):
            status, body = self._response_payload(mod.get_challenge())

        self.assertEqual(status, 200)
        self.assertIn("nonce", body)

        with sqlite3.connect(db_path) as conn:
            row = conn.execute(
                "SELECT request_count FROM attest_challenge_rate_limit WHERE client_ip = ?",
                ("203.0.113.11",),
            ).fetchone()
            self.assertEqual(row[0], 1)


if __name__ == "__main__":
    unittest.main()
