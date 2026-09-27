# SPDX-License-Identifier: MIT
"""
Regression and validation tests for GET /governance/proposals query parameters:
- Validates that non-integer limit returns HTTP 400 with 'limit must be an integer'
- Validates that limit < 1 returns HTTP 400 with 'limit must be >= 1'
- Validates that non-integer offset returns HTTP 400 with 'offset must be an integer'
- Validates that offset < 0 returns HTTP 400 with 'offset must be >= 0'
- Validates that oversized offset (> 64-bit int max) returns HTTP 400 with 'offset out of range' (preventing SQLite OverflowError DoS)
- Validates that valid pagination requests succeed cleanly
"""

import gc
import json
import os
import sqlite3
import sys
import tempfile
import unittest

_NODE_PY = os.path.join(os.path.dirname(__file__), "rustchain_v2_integrated_v2.2.1_rip200.py")

class TestGovernanceProposalsValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._db_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        cls._db_tmp.close()

        # Seed minimal db
        conn = sqlite3.connect(cls._db_tmp.name)
        conn.execute(
            """CREATE TABLE IF NOT EXISTS governance_proposals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                proposer_wallet TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                activated_at INTEGER,
                ends_at INTEGER,
                status TEXT NOT NULL DEFAULT 'draft',
                yes_weight REAL NOT NULL DEFAULT 0,
                no_weight REAL NOT NULL DEFAULT 0
            )"""
        )
        conn.execute(
            "INSERT INTO governance_proposals (proposer_wallet, title, description, created_at, status) "
            "VALUES (?, ?, ?, ?, ?)",
            ("RTC" + "0" * 40, "Test Proposal", "Test Description", 1000000, "active")
        )
        conn.commit()
        conn.close()

        # Import node module
        os.environ.setdefault("RC_ADMIN_KEY", "a" * 64)
        os.environ["RUSTCHAIN_DB_PATH"] = cls._db_tmp.name
        node_dir = os.path.dirname(os.path.abspath(_NODE_PY))
        if node_dir not in sys.path:
            sys.path.insert(0, node_dir)

        import importlib.util
        spec = importlib.util.spec_from_file_location("rustchain_node_gov_val", _NODE_PY)
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)
        cls.client = cls.module.app.test_client()

    @classmethod
    def tearDownClass(cls):
        gc.collect()
        try:
            os.unlink(cls._db_tmp.name)
        except (PermissionError, OSError):
            pass

    def test_invalid_limit_string_returns_400(self):
        resp = self.client.get("/governance/proposals?limit=banana")
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertFalse(data.get("ok"))
        self.assertIn("limit must be an integer", data.get("error", ""))

    def test_zero_limit_returns_400(self):
        resp = self.client.get("/governance/proposals?limit=0")
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertFalse(data.get("ok"))
        self.assertIn("limit must be >= 1", data.get("error", ""))

    def test_negative_limit_returns_400(self):
        resp = self.client.get("/governance/proposals?limit=-5")
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertFalse(data.get("ok"))
        self.assertIn("limit must be >= 1", data.get("error", ""))

    def test_invalid_offset_string_returns_400(self):
        resp = self.client.get("/governance/proposals?offset=invalid")
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertFalse(data.get("ok"))
        self.assertIn("offset must be an integer", data.get("error", ""))

    def test_negative_offset_returns_400(self):
        resp = self.client.get("/governance/proposals?offset=-1")
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertFalse(data.get("ok"))
        self.assertIn("offset must be >= 0", data.get("error", ""))

    def test_overflow_offset_returns_400(self):
        resp = self.client.get("/governance/proposals?offset=9999999999999999999999999999999999999999")
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertFalse(data.get("ok"))
        self.assertIn("offset out of range", data.get("error", ""))

    def test_valid_params_succeed(self):
        resp = self.client.get("/governance/proposals?limit=10&offset=0")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data.get("ok"))
        self.assertEqual(data.get("limit"), 10)
        self.assertEqual(data.get("offset"), 0)

    def test_empty_params_use_defaults(self):
        resp = self.client.get("/governance/proposals?limit=&offset=")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data.get("ok"))
        self.assertEqual(data.get("limit"), 50)
        self.assertEqual(data.get("offset"), 0)

if __name__ == "__main__":
    unittest.main()
