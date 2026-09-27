# SPDX-License-Identifier: MIT
"""ergo_miner_anchor: no wallet password in source, and every anchor stores the
exact preimage of its commitment so an outside auditor can recompute it."""
import importlib.util
import json
import os
import sys
import types
import unittest
from hashlib import blake2b
from pathlib import Path

NODE = Path(__file__).resolve().parents[1]
SRC = NODE / "ergo_miner_anchor.py"


def _load():
    # beacon_anchor is imported at module load; the pure functions under test
    # don't need it, so stub it if its deps are unavailable.
    sys.path.insert(0, str(NODE))
    if "beacon_anchor" not in sys.modules:
        try:
            import beacon_anchor  # noqa: F401
        except Exception:
            stub = types.ModuleType("beacon_anchor")
            stub.compute_beacon_digest = lambda *_a, **_k: {"count": 0, "ids": []}
            stub.mark_anchored = lambda *_a, **_k: None
            stub.init_beacon_table = lambda *_a, **_k: None
            sys.modules["beacon_anchor"] = stub
    spec = importlib.util.spec_from_file_location("ergo_miner_anchor_under_test", SRC)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class ErgoMinerAnchorAuditabilityTest(unittest.TestCase):
    def test_no_hardcoded_wallet_password(self):
        src = SRC.read_text(encoding="utf-8")
        self.assertNotIn("rustchain123", src)
        mod = _load()
        import inspect
        self.assertIsNone(inspect.signature(mod.ErgoMinerAnchor.unlock_wallet)
                          .parameters["password"].default)

    def test_locked_wallet_without_password_does_not_post_unlock(self):
        mod = _load()
        posts = []

        class _Resp:
            def json(self):
                return {"isUnlocked": False}

        class _Session:
            headers = {}

            def get(self, *_a, **_k):
                return _Resp()

            def post(self, *a, **k):
                posts.append((a, k))

        a = mod.ErgoMinerAnchor.__new__(mod.ErgoMinerAnchor)
        a.session = _Session()
        old = mod.ERGO_WALLET_PASS
        mod.ERGO_WALLET_PASS = ""
        try:
            a.unlock_wallet()
        finally:
            mod.ERGO_WALLET_PASS = old
        self.assertEqual(posts, [], "must not POST an empty/default password")

    def test_stored_miner_data_recomputes_the_commitment(self):
        mod = _load()
        a = mod.ErgoMinerAnchor.__new__(mod.ErgoMinerAnchor)
        miners = [{"miner": "RTC" + "ab" * 20, "device_arch": "g4", "ts_ok": 1758300000},
                  {"miner": "dual-g4-125", "device_arch": "g4", "ts_ok": 1758290000}]
        stored = a.canonical_miner_data(miners)          # what goes in ergo_anchors.miner_data
        commitment = a.compute_commitment(miners)
        # An auditor with only the stored row can recompute it:
        self.assertEqual(blake2b(stored.encode(), digest_size=32).hexdigest(), commitment)
        self.assertEqual(json.loads(stored), miners)
        combined = a.compute_combined_commitment(commitment, {"digest": "d" * 64})
        self.assertEqual(combined, blake2b(f"{commitment}|{'d' * 64}".encode(), digest_size=32).hexdigest())

    def test_insert_persists_miner_data(self):
        src = SRC.read_text(encoding="utf-8")
        self.assertIn("miner_data", src.split("INSERT INTO ergo_anchors", 1)[1][:200])


if __name__ == "__main__":
    unittest.main()
