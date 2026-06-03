# SPDX-License-Identifier: MIT

import importlib.util
import gc
import os
import sqlite3
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path

try:
    import nacl.signing
    HAVE_NACL = True
except Exception:
    HAVE_NACL = False


NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULE_PATH = os.path.join(NODE_DIR, "rustchain_v2_integrated_v2.2.1_rip200.py")


class _NoopMetric:
    def __init__(self, *args, **kwargs):
        pass

    def labels(self, *args, **kwargs):
        return self

    inc = dec = set = observe = lambda self, *args, **kwargs: None


@unittest.skipUnless(HAVE_NACL, "pynacl not installed")
class TestIngestRoundRobinAuthorization(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.prev_admin_key = os.environ.get("RC_ADMIN_KEY")
        self.prev_db_path = os.environ.get("RUSTCHAIN_DB_PATH")
        self.prev_disable_p2p = os.environ.get("RUSTCHAIN_DISABLE_P2P_AUTO_START")
        os.environ["RC_ADMIN_KEY"] = "0123456789abcdef0123456789abcdef"
        os.environ["RUSTCHAIN_DB_PATH"] = str(Path(self.tmp.name) / "node.db")
        os.environ["RUSTCHAIN_DISABLE_P2P_AUTO_START"] = "1"

        if NODE_DIR not in sys.path:
            sys.path.insert(0, NODE_DIR)

        self.prev_prometheus_module = sys.modules.get("prometheus_client")
        prometheus_client = types.ModuleType("prometheus_client")
        prometheus_client.Counter = _NoopMetric
        prometheus_client.Gauge = _NoopMetric
        prometheus_client.Histogram = _NoopMetric
        prometheus_client.generate_latest = lambda: b""
        prometheus_client.CONTENT_TYPE_LATEST = "text/plain"
        sys.modules["prometheus_client"] = prometheus_client

        spec = importlib.util.spec_from_file_location(
            "rustchain_ingest_round_robin_node",
            MODULE_PATH,
        )
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)
        self.mod.init_db()
        self.mod.app.config["TESTING"] = True

    def tearDown(self):
        mod = getattr(self, "mod", None)
        if mod is not None:
            try:
                mod.app.do_teardown_appcontext()
            except Exception:
                pass
            block_sync = getattr(mod, "block_sync", None)
            if block_sync is not None:
                stop = getattr(block_sync, "stop", None)
                if callable(stop):
                    stop()
                else:
                    block_sync.running = False
        self.mod = None

        if self.prev_prometheus_module is None:
            sys.modules.pop("prometheus_client", None)
        else:
            sys.modules["prometheus_client"] = self.prev_prometheus_module
        if self.prev_admin_key is None:
            os.environ.pop("RC_ADMIN_KEY", None)
        else:
            os.environ["RC_ADMIN_KEY"] = self.prev_admin_key
        if self.prev_db_path is None:
            os.environ.pop("RUSTCHAIN_DB_PATH", None)
        else:
            os.environ["RUSTCHAIN_DB_PATH"] = self.prev_db_path
        if self.prev_disable_p2p is None:
            os.environ.pop("RUSTCHAIN_DISABLE_P2P_AUTO_START", None)
        else:
            os.environ["RUSTCHAIN_DISABLE_P2P_AUTO_START"] = self.prev_disable_p2p
        for attempt in range(5):
            try:
                self.tmp.cleanup()
                break
            except PermissionError:
                if attempt == 4:
                    raise
                gc.collect()
                time.sleep(0.2)

    def _prepare_consensus_state(self, slot):
        now = int(time.time())
        self.mod.current_slot = lambda: slot

        with sqlite3.connect(self.mod.DB_PATH) as conn:
            # Keep the fixture focused on the route's deployed header-tip shape
            # so failures exercise consensus authorization, not schema setup.
            conn.execute("DROP TABLE IF EXISTS headers")
            conn.execute(
                """CREATE TABLE headers(
                   slot INTEGER PRIMARY KEY,
                   miner_id TEXT NOT NULL,
                   message_hex TEXT NOT NULL,
                   signature_hex TEXT NOT NULL,
                   pubkey_hex TEXT NOT NULL,
                   ts INTEGER NOT NULL
                )"""
            )
            conn.execute(
                """INSERT OR REPLACE INTO miner_attest_recent
                   (miner, ts_ok, device_family, device_arch, fingerprint_passed)
                   VALUES (?, ?, ?, ?, ?)""",
                ("attacker", now, "x86_64", "default", 1),
            )
            conn.execute(
                """INSERT OR REPLACE INTO miner_attest_recent
                   (miner, ts_ok, device_family, device_arch, fingerprint_passed)
                   VALUES (?, ?, ?, ?, ?)""",
                ("victim", now, "x86_64", "default", 1),
            )
            conn.commit()

    def _signed_header_payload(self, miner_id, slot):
        signing_key = nacl.signing.SigningKey.generate()
        pubkey_hex = signing_key.verify_key.encode().hex()
        header = {"slot": slot, "miner": miner_id, "timestamp": int(time.time())}
        signature = signing_key.sign(self.mod.canonical_header_bytes(header)).signature.hex()

        with sqlite3.connect(self.mod.DB_PATH) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO miner_header_keys(miner_id, pubkey_hex) VALUES (?, ?)",
                (miner_id, pubkey_hex),
            )
            conn.commit()

        return {
            "miner_id": miner_id,
            "header": header,
            "signature": signature,
        }

    def test_non_producer_cannot_submit_signed_header_for_slot(self):
        self._prepare_consensus_state(slot=101)
        payload = self._signed_header_payload("attacker", slot=101)

        with self.mod.app.test_client() as client:
            response = client.post("/headers/ingest_signed", json=payload)

        self.assertEqual(response.status_code, 403)
        body = response.get_json()
        self.assertEqual(body["error"], "not_slot_producer")
        self.assertEqual(body["reason"], "not_your_turn")
        self.assertEqual(body["slot_producer"], "victim")

    def test_designated_producer_can_submit_signed_header_for_slot(self):
        self._prepare_consensus_state(slot=100)
        payload = self._signed_header_payload("attacker", slot=100)

        with self.mod.app.test_client() as client:
            response = client.post("/headers/ingest_signed", json=payload)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["ok"])


if __name__ == "__main__":
    unittest.main()
