# SPDX-License-Identifier: MIT
"""
Regression tests for #4311: BCOS directory pagination validation.

Verifies that malformed limit/offset parameters return 400 instead of 500.
"""

import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from bcos_routes import bcos_bp, init_bcos_table, register_bcos_routes

try:
    from flask import Flask
except ImportError:
    Flask = None


@unittest.skipIf(Flask is None, "flask not installed")
class TestBcosPagination(unittest.TestCase):
    """Regression tests for BCOS directory pagination (#4311)."""

    def setUp(self):
        self.app = Flask(__name__)
        self.app.config["TESTING"] = True
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.db_fd)
        with sqlite3.connect(self.db_path) as conn:
            init_bcos_table(conn)
        register_bcos_routes(self.app, self.db_path)
        self.client = self.app.test_client()

    def tearDown(self):
        os.unlink(self.db_path)

    # ── limit ────────────────────────────────────────────────
    def test_limit_non_integer_returns_400(self):
        """limit=abc should return 400, not 500."""
        r = self.client.get("/bcos/directory?limit=abc")
        self.assertEqual(r.status_code, 400)
        data = json.loads(r.data)
        self.assertEqual(data["error"], "invalid_pagination")

    def test_limit_negative_returns_400(self):
        """limit=-1 should return 400."""
        r = self.client.get("/bcos/directory?limit=-1")
        self.assertEqual(r.status_code, 400)
        data = json.loads(r.data)
        self.assertEqual(data["error"], "invalid_pagination")

    def test_limit_zero_returns_empty(self):
        """limit=0 is valid and returns empty list."""
        r = self.client.get("/bcos/directory?limit=0")
        self.assertEqual(r.status_code, 200)

    def test_limit_clamped_to_max(self):
        """limit=9999 should be clamped to 500."""
        r = self.client.get("/bcos/directory?limit=9999")
        self.assertEqual(r.status_code, 200)

    def test_limit_float_returns_400(self):
        """limit=1.5 should return 400."""
        r = self.client.get("/bcos/directory?limit=1.5")
        self.assertEqual(r.status_code, 400)

    # ── offset ───────────────────────────────────────────────
    def test_offset_non_integer_returns_400(self):
        """offset=abc should return 400, not 500."""
        r = self.client.get("/bcos/directory?offset=abc")
        self.assertEqual(r.status_code, 400)
        data = json.loads(r.data)
        self.assertEqual(data["error"], "invalid_pagination")

    def test_offset_negative_returns_400(self):
        """offset=-1 should return 400."""
        r = self.client.get("/bcos/directory?offset=-1")
        self.assertEqual(r.status_code, 400)

    # ── combined ─────────────────────────────────────────────
    def test_valid_pagination(self):
        """Valid limit + offset should succeed."""
        r = self.client.get("/bcos/directory?limit=10&offset=0")
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.data)
        self.assertTrue(data["ok"])

    def test_default_pagination(self):
        """No params should use defaults (limit=100, offset=0)."""
        r = self.client.get("/bcos/directory")
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.data)
        self.assertEqual(data["offset"], 0)


if __name__ == "__main__":
    unittest.main()
