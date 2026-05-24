import importlib.util
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock

NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULE_PATH = os.path.join(NODE_DIR, "rustchain_v2_integrated_v2.2.1_rip200.py")
ADMIN_KEY = "0123456789abcdef0123456789abcdef"


class TestIntegratedP2PBlocksPagination(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls._prev_db_path = os.environ.get("RUSTCHAIN_DB_PATH")
        cls._prev_admin_key = os.environ.get("RC_ADMIN_KEY")
        cls._prev_disable_p2p = os.environ.get("RUSTCHAIN_DISABLE_P2P_AUTO_START")
        os.environ["RUSTCHAIN_DB_PATH"] = os.path.join(cls._tmp.name, "import.db")
        os.environ["RC_ADMIN_KEY"] = ADMIN_KEY
        os.environ["RUSTCHAIN_DISABLE_P2P_AUTO_START"] = "1"

        if NODE_DIR not in sys.path:
            sys.path.insert(0, NODE_DIR)

        spec = importlib.util.spec_from_file_location("rustchain_integrated_p2p_blocks_test", MODULE_PATH)
        cls.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.mod)
        cls.client = cls.mod.app.test_client()

    @classmethod
    def tearDownClass(cls):
        for key, value in (
            ("RUSTCHAIN_DB_PATH", cls._prev_db_path),
            ("RC_ADMIN_KEY", cls._prev_admin_key),
            ("RUSTCHAIN_DISABLE_P2P_AUTO_START", cls._prev_disable_p2p),
        ):
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        cls._tmp.cleanup()

    def setUp(self):
        self._original_auth = self.mod.app.view_functions["p2p_get_blocks"]
        self.mod.app.view_functions["p2p_get_blocks"] = self._original_auth.__wrapped__

    def tearDown(self):
        self.mod.app.view_functions["p2p_get_blocks"] = self._original_auth

    def test_rejects_non_integer_start(self):
        resp = self.client.get("/p2p/blocks?start=abc")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json(), {"ok": False, "error": "start must be an integer"})

    def test_rejects_negative_start(self):
        resp = self.client.get("/p2p/blocks?start=-1")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json(), {"ok": False, "error": "start must be >= 0"})

    def test_rejects_non_integer_limit(self):
        resp = self.client.get("/p2p/blocks?limit=abc")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json(), {"ok": False, "error": "limit must be an integer"})

    def test_rejects_negative_limit_before_sync_query(self):
        self.mod.block_sync.get_blocks_for_sync = MagicMock(return_value=[])

        resp = self.client.get("/p2p/blocks?start=0&limit=-1")

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json(), {"ok": False, "error": "limit must be >= 1"})
        self.mod.block_sync.get_blocks_for_sync.assert_not_called()

    def test_caps_oversized_limit(self):
        self.mod.block_sync.get_blocks_for_sync = MagicMock(return_value=[])

        resp = self.client.get("/p2p/blocks?start=7&limit=5000")

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json(), {"ok": True, "blocks": []})
        self.mod.block_sync.get_blocks_for_sync.assert_called_once_with(7, 1000)


if __name__ == "__main__":
    unittest.main()
