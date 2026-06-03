# SPDX-License-Identifier: MIT

import importlib.util
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULE_PATH = os.path.join(NODE_DIR, "rustchain_v2_integrated_v2.2.1_rip200.py")


class TestMinerHeaderKeySchema(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._prev_admin_key = os.environ.get("RC_ADMIN_KEY")
        self._prev_db_path = os.environ.get("RUSTCHAIN_DB_PATH")
        self._prev_disable_p2p = os.environ.get("RUSTCHAIN_DISABLE_P2P_AUTO_START")
        os.environ["RC_ADMIN_KEY"] = "0123456789abcdef0123456789abcdef"
        os.environ["RUSTCHAIN_DISABLE_P2P_AUTO_START"] = "1"
        self.db_path = str(Path(self._tmp.name) / "fresh-node.db")
        os.environ["RUSTCHAIN_DB_PATH"] = self.db_path

        if NODE_DIR not in sys.path:
            sys.path.insert(0, NODE_DIR)

        spec = importlib.util.spec_from_file_location(
            "rustchain_headerkey_schema_node",
            MODULE_PATH,
        )
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)
        self.mod.DB_PATH = self.db_path
        self.mod.init_db()
        self.mod.app.config["TESTING"] = True

    def tearDown(self):
        if self._prev_admin_key is None:
            os.environ.pop("RC_ADMIN_KEY", None)
        else:
            os.environ["RC_ADMIN_KEY"] = self._prev_admin_key
        if self._prev_db_path is None:
            os.environ.pop("RUSTCHAIN_DB_PATH", None)
        else:
            os.environ["RUSTCHAIN_DB_PATH"] = self._prev_db_path
        if self._prev_disable_p2p is None:
            os.environ.pop("RUSTCHAIN_DISABLE_P2P_AUTO_START", None)
        else:
            os.environ["RUSTCHAIN_DISABLE_P2P_AUTO_START"] = self._prev_disable_p2p
        self._tmp.cleanup()

    def test_init_db_creates_miner_header_keys_for_headerkey_route(self):
        with sqlite3.connect(self.db_path) as conn:
            table = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='miner_header_keys'",
            ).fetchone()

        self.assertIsNotNone(table)

        with self.mod.app.test_client() as client:
            response = client.post(
                "/miner/headerkey",
                headers={"X-API-Key": "0123456789abcdef0123456789abcdef"},
                json={"miner_id": "miner-1", "pubkey_hex": "a" * 64},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["ok"], True)

        with sqlite3.connect(self.db_path) as conn:
            stored = conn.execute(
                "SELECT pubkey_hex FROM miner_header_keys WHERE miner_id = ?",
                ("miner-1",),
            ).fetchone()

        self.assertEqual(stored, ("a" * 64,))


if __name__ == "__main__":
    unittest.main()
