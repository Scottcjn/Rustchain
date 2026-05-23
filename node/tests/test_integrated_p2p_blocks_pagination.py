# SPDX-License-Identifier: MIT

import hmac
import hashlib
import importlib.util
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path


NODE_DIR = Path(__file__).resolve().parents[1]
MODULE_PATH = NODE_DIR / "rustchain_v2_integrated_v2.2.1_rip200.py"
P2P_KEY = "integration-p2p-blocks-test-key"


class RecordingBlockSync:
    def __init__(self):
        self.calls = []

    def get_blocks_for_sync(self, start_height, limit):
        self.calls.append((start_height, limit))
        return [{"block_index": start_height, "limit": limit}]


class TestIntegratedP2PBlocksPagination(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls._prev_db_path = os.environ.get("RUSTCHAIN_DB_PATH")
        cls._prev_admin_key = os.environ.get("RC_ADMIN_KEY")
        cls._prev_p2p_key = os.environ.get("RC_P2P_KEY")
        cls._prev_disable_p2p = os.environ.get("RUSTCHAIN_DISABLE_P2P_AUTO_START")

        os.environ["RUSTCHAIN_DB_PATH"] = str(Path(cls._tmp.name) / "node.db")
        os.environ["RC_ADMIN_KEY"] = "0" * 32
        os.environ["RC_P2P_KEY"] = P2P_KEY
        os.environ["RUSTCHAIN_DISABLE_P2P_AUTO_START"] = "1"

        if str(NODE_DIR) not in sys.path:
            sys.path.insert(0, str(NODE_DIR))

        spec = importlib.util.spec_from_file_location(
            "rustchain_integrated_p2p_blocks_pagination_test",
            MODULE_PATH,
        )
        cls.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.mod)
        cls.client = cls.mod.app.test_client()
        cls.block_sync = RecordingBlockSync()
        cls.mod.block_sync = cls.block_sync

    @classmethod
    def tearDownClass(cls):
        for name, value in (
            ("RUSTCHAIN_DB_PATH", cls._prev_db_path),
            ("RC_ADMIN_KEY", cls._prev_admin_key),
            ("RC_P2P_KEY", cls._prev_p2p_key),
            ("RUSTCHAIN_DISABLE_P2P_AUTO_START", cls._prev_disable_p2p),
        ):
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        cls._tmp.cleanup()

    def setUp(self):
        self.block_sync.calls.clear()

    def _auth_headers(self):
        timestamp = str(int(time.time()))
        signature = hmac.new(
            P2P_KEY.encode("utf-8"),
            timestamp.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return {
            "X-Peer-Signature": signature,
            "X-Peer-Timestamp": timestamp,
        }

    def get_blocks(self, query):
        return self.client.get(f"/p2p/blocks?{query}", headers=self._auth_headers())

    def test_blocks_rejects_negative_start(self):
        response = self.get_blocks("start=-1")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json(), {"ok": False, "error": "start must be >= 0"})
        self.assertEqual(self.block_sync.calls, [])

    def test_blocks_rejects_negative_limit(self):
        response = self.get_blocks("limit=-1")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json(), {"ok": False, "error": "limit must be >= 1"})
        self.assertEqual(self.block_sync.calls, [])

    def test_blocks_rejects_non_integer_start(self):
        response = self.get_blocks("start=abc")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json(),
            {"ok": False, "error": "start must be an integer"},
        )
        self.assertEqual(self.block_sync.calls, [])

    def test_blocks_rejects_non_integer_limit(self):
        response = self.get_blocks("limit=notanumber")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json(),
            {"ok": False, "error": "limit must be an integer"},
        )
        self.assertEqual(self.block_sync.calls, [])

    def test_blocks_caps_oversized_limit_before_sync(self):
        response = self.get_blocks("start=7&limit=5000")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.block_sync.calls, [(7, 1000)])
        self.assertEqual(
            response.get_json(),
            {"ok": True, "blocks": [{"block_index": 7, "limit": 1000}]},
        )


if __name__ == "__main__":
    unittest.main()
