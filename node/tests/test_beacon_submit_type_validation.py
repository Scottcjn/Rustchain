# SPDX-License-Identifier: MIT

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path


NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULE_PATH = os.path.join(NODE_DIR, "rustchain_v2_integrated_v2.2.1_rip200.py")


class TestBeaconSubmitTypeValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.prev_env = {
            key: os.environ.get(key)
            for key in (
                "RUSTCHAIN_DB_PATH",
                "RC_ADMIN_KEY",
                "RUSTCHAIN_DISABLE_P2P_AUTO_START",
            )
        }
        os.environ["RUSTCHAIN_DB_PATH"] = str(Path(cls.tmp.name) / "node.db")
        os.environ["RC_ADMIN_KEY"] = "0123456789abcdef0123456789abcdef"
        os.environ["RUSTCHAIN_DISABLE_P2P_AUTO_START"] = "1"

        if NODE_DIR not in sys.path:
            sys.path.insert(0, NODE_DIR)

        spec = importlib.util.spec_from_file_location(
            "rustchain_beacon_submit_type_validation_node",
            MODULE_PATH,
        )
        cls.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.mod)
        cls.mod.app.config["TESTING"] = True
        cls.client = cls.mod.app.test_client()

    @classmethod
    def tearDownClass(cls):
        mod = getattr(cls, "mod", None)
        if mod is not None:
            block_sync = getattr(mod, "block_sync", None)
            if block_sync is not None:
                stop = getattr(block_sync, "stop", None)
                if callable(stop):
                    stop()
                else:
                    block_sync.running = False
        for key, value in cls.prev_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        cls.tmp.cleanup()

    def setUp(self):
        self.mod._BEACON_IP_RATE_LIMIT_BUCKETS.clear()

    def _valid_payload(self):
        return {
            "agent_id": "agent-alpha",
            "kind": "hello",
            "nonce": "nonce-123",
            "sig": "a" * 64,
            "pubkey": "b" * 64,
        }

    def test_beacon_submit_rejects_truthy_non_string_fields(self):
        invalid_values = {
            "agent_id": {"value": "agent-alpha"},
            "kind": ["hello"],
            "nonce": 123456,
            "sig": ["a" * 64],
            "pubkey": {"hex": "b" * 64},
        }

        for field_name, invalid_value in invalid_values.items():
            with self.subTest(field_name=field_name):
                payload = self._valid_payload()
                payload[field_name] = invalid_value

                response = self.client.post("/beacon/submit", json=payload)

                self.assertEqual(response.status_code, 400)
                self.assertEqual(
                    response.get_json(),
                    {
                        "ok": False,
                        "error": f"invalid_field_type:{field_name}",
                    },
                )


if __name__ == "__main__":
    unittest.main()
