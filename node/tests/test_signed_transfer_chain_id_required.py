# SPDX-License-Identifier: MIT
"""Regression: /wallet/transfer/signed must bind chain_id to prevent cross-network
replay.

chain_id was OPTIONAL and only bound into the signed message `if chain_id:`. A
client that OMITTED it signed a chain-less message with no network binding, so the
same signature replays across networks (testnet <-> mainnet, forks) — real theft
under the common case of cross-network key reuse. The fix requires chain binding by
default, with RC_ALLOW_CHAINLESS_SIGNED_TRANSFER=1 as an explicit transition hatch.

The chain_id gate runs BEFORE signature verification (right after the review gate),
so these tests reach it with a dummy signature, like the blocked-wallet freeze test.
"""
import gc
import importlib.util
import os
import shutil
import sqlite3
import sys
import tempfile
import time
import unittest

NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULE_PATH = os.path.join(NODE_DIR, "rustchain_v2_integrated_v2.2.1_rip200.py")

SENDER = "RTC" + "c" * 40   # valid form, NOT under review -> passes the review gate
DEST = "RTC" + "d" * 40


class TestSignedTransferChainIdRequired(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.mkdtemp(prefix="chainid-")
        cls._prev = {k: os.environ.get(k) for k in
                     ("RUSTCHAIN_DB_PATH", "RC_ADMIN_KEY", "RC_ALLOW_CHAINLESS_SIGNED_TRANSFER")}
        os.environ["RUSTCHAIN_DB_PATH"] = os.path.join(cls._tmp, "import.db")
        os.environ["RC_ADMIN_KEY"] = "0123456789abcdef0123456789abcdef"
        os.environ.pop("RC_ALLOW_CHAINLESS_SIGNED_TRANSFER", None)
        if NODE_DIR not in sys.path:
            sys.path.insert(0, NODE_DIR)
        spec = importlib.util.spec_from_file_location("rc_chainid_test", MODULE_PATH)
        cls.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.mod)
        cls.client = cls.mod.app.test_client()
        # ensure review tables exist + empty (SENDER not blocked)
        with sqlite3.connect(cls.mod.DB_PATH) as conn:
            cls.mod.ensure_wallet_review_tables(conn)
            conn.commit()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.mod.app.do_teardown_appcontext()
        except Exception:
            pass
        cls.client = None
        cls.mod = None
        for k, v in cls._prev.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        gc.collect()
        shutil.rmtree(cls._tmp, ignore_errors=True)

    def _post(self, chain_id=None, nonce=None):
        body = {
            "from_address": SENDER,
            "to_address": DEST,
            "amount_rtc": 1,
            "nonce": nonce if nonce is not None else int(time.time() * 1000),
            "signature": "00",           # dummy — the chain_id gate is reached first
            "public_key": "00" * 32,
        }
        if chain_id is not None:
            body["chain_id"] = chain_id
        return self.client.post("/wallet/transfer/signed", json=body)

    def test_chainless_rejected_by_default(self):
        os.environ.pop("RC_ALLOW_CHAINLESS_SIGNED_TRANSFER", None)
        resp = self._post(chain_id=None)
        self.assertEqual(resp.status_code, 400, resp.get_json())
        self.assertEqual(resp.get_json().get("code"), "CHAIN_ID_REQUIRED")

    def test_wrong_chain_id_rejected(self):
        resp = self._post(chain_id="rustchain-not-a-real-network")
        self.assertEqual(resp.status_code, 400, resp.get_json())
        self.assertIn("does not match", resp.get_json().get("error", ""))

    def test_correct_chain_id_passes_gate(self):
        """Correct chain_id must get PAST the chain gate (then fail downstream at
        pubkey/signature, since the dummy key/sig don't match) — not CHAIN_ID_REQUIRED."""
        resp = self._post(chain_id=self.mod.CHAIN_ID)
        self.assertNotEqual(resp.get_json().get("code"), "CHAIN_ID_REQUIRED")
        # downstream rejection (pubkey mismatch / invalid signature), gate passed
        self.assertIn(resp.status_code, (400, 401))

    def test_transition_flag_allows_chainless(self):
        os.environ["RC_ALLOW_CHAINLESS_SIGNED_TRANSFER"] = "1"
        try:
            resp = self._post(chain_id=None)
            self.assertNotEqual(resp.get_json().get("code"), "CHAIN_ID_REQUIRED",
                                "flag set: chain-less must pass the gate")
            self.assertIn(resp.status_code, (400, 401))  # fails later at sig, not the gate
        finally:
            os.environ.pop("RC_ALLOW_CHAINLESS_SIGNED_TRANSFER", None)


if __name__ == "__main__":
    unittest.main()
