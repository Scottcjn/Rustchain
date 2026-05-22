# SPDX-License-Identifier: MIT

import hmac
import hashlib
import importlib.util
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path


NODE_DIR = Path(__file__).resolve().parents[1]
MODULE_PATH = NODE_DIR / "rustchain_v2_integrated_v2.2.1_rip200.py"
P2P_KEY = "integration-p2p-test-key"


class TestIntegratedP2PAddPeer(unittest.TestCase):
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
            "rustchain_integrated_p2p_add_peer_test",
            MODULE_PATH,
        )
        cls.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.mod)
        cls.client = cls.mod.app.test_client()

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

    def _auth_headers(self, body):
        timestamp = str(int(time.time()))
        signature = hmac.new(
            P2P_KEY.encode("utf-8"),
            f"{body}{timestamp}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return {
            "Content-Type": "application/json",
            "X-Peer-Signature": signature,
            "X-Peer-Timestamp": timestamp,
        }

    def post_add_peer(self, payload):
        body = json.dumps(payload)
        return self.client.post(
            "/p2p/add_peer",
            data=body,
            headers=self._auth_headers(body),
        )

    def test_add_peer_rejects_non_object_json(self):
        response = self.post_add_peer(["peer_url", "http://peer.example:8088"])

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json(),
            {"ok": False, "error": "JSON object required"},
        )

    def test_add_peer_rejects_non_string_peer_url(self):
        response = self.post_add_peer({"peer_url": ["http://peer.example:8088"]})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json(),
            {"ok": False, "error": "peer_url must be a string"},
        )

    def test_add_peer_returns_boolean_ok_for_secure_peer_manager(self):
        response = self.post_add_peer({"peer_url": "http://peer.example:8088"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(),
            {"ok": True, "message": "Peer added successfully"},
        )


if __name__ == "__main__":
    unittest.main()
