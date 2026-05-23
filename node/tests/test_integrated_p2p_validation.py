import importlib.util
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock

NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULE_PATH = os.path.join(NODE_DIR, "rustchain_v2_integrated_v2.2.1_rip200.py")


class TestIntegratedP2PValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls._prev_db_path = os.environ.get("RUSTCHAIN_DB_PATH")
        cls._prev_auto_start = os.environ.get("RUSTCHAIN_DISABLE_P2P_AUTO_START")
        cls._prev_admin_key = os.environ.get("RC_ADMIN_KEY")
        os.environ["RUSTCHAIN_DB_PATH"] = os.path.join(cls._tmp.name, "import.db")
        os.environ["RUSTCHAIN_DISABLE_P2P_AUTO_START"] = "1"
        os.environ["RC_ADMIN_KEY"] = "0123456789abcdef0123456789abcdef"

        if NODE_DIR not in sys.path:
            sys.path.insert(0, NODE_DIR)

        spec = importlib.util.spec_from_file_location("rustchain_integrated_p2p_validation_test", MODULE_PATH)
        cls.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.mod)
        cls.client = cls.mod.app.test_client()

    @classmethod
    def tearDownClass(cls):
        if cls._prev_db_path is None:
            os.environ.pop("RUSTCHAIN_DB_PATH", None)
        else:
            os.environ["RUSTCHAIN_DB_PATH"] = cls._prev_db_path
        if cls._prev_auto_start is None:
            os.environ.pop("RUSTCHAIN_DISABLE_P2P_AUTO_START", None)
        else:
            os.environ["RUSTCHAIN_DISABLE_P2P_AUTO_START"] = cls._prev_auto_start
        if cls._prev_admin_key is None:
            os.environ.pop("RC_ADMIN_KEY", None)
        else:
            os.environ["RC_ADMIN_KEY"] = cls._prev_admin_key
        cls._tmp.cleanup()

    def setUp(self):
        self.mod.block_sync.get_blocks_for_sync = MagicMock(return_value=[])

    @staticmethod
    def _allow_peer_auth(func):
        return func.__wrapped__ if hasattr(func, "__wrapped__") else func

    def test_integrated_p2p_blocks_rejects_unsafe_pagination_before_sync(self):
        with self.mod.app.test_request_context("/p2p/blocks?start=0&limit=-1"):
            response, status = self._allow_peer_auth(self.mod.p2p_get_blocks)()

        self.assertEqual(status, 400)
        self.assertEqual(response.get_json(), {"ok": False, "error": "limit must be >= 1"})
        self.mod.block_sync.get_blocks_for_sync.assert_not_called()

    def test_integrated_p2p_blocks_caps_oversized_limit(self):
        with self.mod.app.test_request_context("/p2p/blocks?start=0&limit=5000"):
            response = self._allow_peer_auth(self.mod.p2p_get_blocks)()

        self.assertEqual(response.get_json(), {"ok": True, "blocks": []})
        self.mod.block_sync.get_blocks_for_sync.assert_called_once_with(0, 1000)

    def test_integrated_add_peer_rejects_non_object_json(self):
        with self.mod.app.test_request_context("/p2p/add_peer", method="POST", json=[]):
            response, status = self._allow_peer_auth(self.mod.p2p_add_peer)()

        self.assertEqual(status, 400)
        self.assertEqual(response.get_json(), {"ok": False, "error": "JSON body must be an object"})

    def test_integrated_add_peer_returns_boolean_ok_and_message(self):
        self.mod.peer_manager.add_peer = MagicMock(return_value=(True, "Peer added successfully"))

        with self.mod.app.test_request_context("/p2p/add_peer", method="POST", json={"peer_url": "http://peer.example:8088"}):
            response = self._allow_peer_auth(self.mod.p2p_add_peer)()

        self.assertEqual(response.get_json(), {"ok": True, "message": "Peer added successfully"})


if __name__ == "__main__":
    unittest.main()
