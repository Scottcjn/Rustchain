# SPDX-License-Identifier: MIT
"""
Regression (audit A1): an unsigned / legacy re-attest must NOT erase a pinned
signing key.

record_attestation_success() upserts miner_attest_recent with
`signing_pubkey = excluded.signing_pubkey`. The /attest/submit handler passes
pin_pubkey=None whenever it decides not to ADD a key (already pinned, frozen,
grandfathered, or the submission was unsigned) and its comment says COALESCE
keeps the existing pin - but the SQL did not COALESCE, so every unsigned
attest for a miner NULLed the #8016 pin ledger. In the default log_only
enforce mode unsigned submissions are accepted, so anyone could wipe a
victim's pin and then sign as that miner to get pinned themselves.

Fix: signing_pubkey = COALESCE(excluded.signing_pubkey, miner_attest_recent.signing_pubkey)
"""

import importlib.util
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

try:
    import nacl.signing
    HAVE_NACL = True
except Exception:  # pragma: no cover - environment dependent
    HAVE_NACL = False

NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULE_PATH = os.path.join(NODE_DIR, "rustchain_v2_integrated_v2.2.1_rip200.py")

EXTRA_SCHEMA = [
    "CREATE TABLE IF NOT EXISTS blocked_wallets (wallet TEXT PRIMARY KEY, reason TEXT)",
    "CREATE TABLE IF NOT EXISTS ip_rate_limit (client_ip TEXT NOT NULL, miner_id TEXT NOT NULL, ts INTEGER NOT NULL, PRIMARY KEY (client_ip, miner_id))",
    "CREATE TABLE IF NOT EXISTS miner_attest_recent (miner TEXT PRIMARY KEY, ts_ok INTEGER NOT NULL, device_family TEXT, device_arch TEXT, entropy_score REAL DEFAULT 0, fingerprint_passed INTEGER DEFAULT 0, source_ip TEXT, warthog_bonus REAL DEFAULT 1.0)",
    "CREATE TABLE IF NOT EXISTS hardware_bindings (hardware_id TEXT PRIMARY KEY, bound_miner TEXT NOT NULL, device_arch TEXT, device_model TEXT, bound_at INTEGER NOT NULL, attestation_count INTEGER DEFAULT 0)",
    "CREATE TABLE IF NOT EXISTS miner_header_keys (miner_id TEXT PRIMARY KEY, pubkey_hex TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS miner_macs (miner TEXT NOT NULL, mac_hash TEXT NOT NULL, first_ts INTEGER NOT NULL, last_ts INTEGER NOT NULL, count INTEGER NOT NULL DEFAULT 1, PRIMARY KEY (miner, mac_hash))",
]


def _sign_message(miner_id, wallet, nonce, commitment):
    signing_key = nacl.signing.SigningKey.generate()
    pubkey_hex = signing_key.verify_key.encode().hex()
    message = "{}|{}|{}|{}".format(miner_id, wallet, nonce, commitment)
    return signing_key.sign(message.encode("utf-8")).signature.hex(), pubkey_hex


class TestPinSurvivesUnsignedAttest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls._prev_env = {k: os.environ.get(k) for k in ("RC_ADMIN_KEY", "RUSTCHAIN_DB_PATH", "DB_PATH", "RTC_ATTEST_ENFORCE_MODE")}
        os.environ["RC_ADMIN_KEY"] = "0123456789abcdef0123456789abcdef"
        # The vulnerable path is the default rollout phase: unsigned attests accepted.
        os.environ["RTC_ATTEST_ENFORCE_MODE"] = "log_only"
        if NODE_DIR not in sys.path:
            sys.path.insert(0, NODE_DIR)

    @classmethod
    def tearDownClass(cls):
        for k, v in cls._prev_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        cls._tmp.cleanup()

    def _load_module(self, module_name, db_name):
        db_path = str(Path(self._tmp.name) / db_name)
        os.environ["RUSTCHAIN_DB_PATH"] = db_path
        os.environ["DB_PATH"] = db_path
        spec = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.DB_PATH = db_path
        # Same identical-fingerprint replay heuristic every attest harness disables;
        # it is orthogonal to the pin ledger under test.
        mod.HAVE_REPLAY_DEFENSE = False
        mod.init_db()
        with sqlite3.connect(db_path) as conn:
            for stmt in EXTRA_SCHEMA:
                conn.execute(stmt)
            conn.commit()
        return mod, db_path

    def _get_challenge(self, mod):
        with mod.app.test_request_context("/attest/challenge", method="POST", json={}):
            return mod.get_challenge().get_json()["nonce"]

    def _submit(self, mod, payload):
        with mod.app.test_request_context("/attest/submit", method="POST", json=payload):
            resp = mod._submit_attestation_impl()
        if isinstance(resp, tuple):
            body, status = resp
            return status, body.get_json()
        return resp.status_code, resp.get_json()

    @staticmethod
    def _payload(miner, nonce, commitment="deadbeef", sig_hex=None, pubkey_hex=None, miner_id=None):
        payload = {
            "miner": miner,
            "report": {"nonce": nonce, "commitment": commitment},
            "device": {"family": "x86_64", "arch": "default", "model": "test-box", "cores": 4},
            "signals": {"hostname": "test-host", "macs": []},
            "fingerprint": {
                "checks": {
                    "anti_emulation": {"passed": True, "data": {"vm_indicators": []}},
                    "clock_drift": {"passed": True, "data": {"cv": 0.05, "samples": 64}},
                },
                "all_passed": True,
            },
        }
        if sig_hex is not None:
            payload["signature"] = sig_hex
        if pubkey_hex is not None:
            payload["public_key"] = pubkey_hex
        if miner_id is not None:
            payload["miner_id"] = miner_id
        return payload

    @staticmethod
    def _pinned_key(db_path, miner):
        with sqlite3.connect(db_path) as conn:
            row = conn.execute(
                "SELECT signing_pubkey FROM miner_attest_recent WHERE miner = ?", (miner,)
            ).fetchone()
        return row[0] if row else None

    @unittest.skipUnless(HAVE_NACL, "pynacl not installed")
    def test_unsigned_attest_keeps_pinned_key(self):
        """Signed attest pins a key; a later unsigned attest must leave it intact."""
        mod, db_path = self._load_module("rustchain_attest_pin_survives", "pin_survives.db")
        miner = "pin-survivor-miner"  # brand-new symbolic identity -> TOFU pin allowed
        miner_id = "pin-survivor-miner"

        nonce = self._get_challenge(mod)
        sig_hex, pubkey_hex = _sign_message(miner_id, miner, nonce, "deadbeef")
        status, body = self._submit(mod, self._payload(miner, nonce, "deadbeef", sig_hex, pubkey_hex, miner_id))
        self.assertEqual(status, 200, body)
        self.assertEqual(self._pinned_key(db_path, miner), pubkey_hex)

        # Attacker (or a legacy client) re-attests the same identity WITHOUT a signature.
        nonce2 = self._get_challenge(mod)
        status, body = self._submit(mod, self._payload(miner, nonce2, "cafebabe", miner_id=miner_id))
        self.assertEqual(status, 200, body)

        self.assertEqual(
            self._pinned_key(db_path, miner), pubkey_hex,
            "unsigned re-attest NULLed the pinned signing key (audit A1)",
        )

    def test_record_attestation_success_upsert_coalesces_pin(self):
        """Direct UPSERT check: signing_pubkey=None on conflict keeps the stored pin."""
        mod, db_path = self._load_module("rustchain_attest_pin_upsert", "pin_upsert.db")
        miner = "upsert-miner"
        device = {"family": "x86_64", "arch": "default", "model": "test-box", "cores": 4}
        mod.record_attestation_success(miner, device, True, "127.0.0.1", fingerprint={}, signing_pubkey="ab" * 32)
        self.assertEqual(self._pinned_key(db_path, miner), "ab" * 32)

        mod.record_attestation_success(miner, device, True, "127.0.0.1", fingerprint={}, signing_pubkey=None)
        self.assertEqual(self._pinned_key(db_path, miner), "ab" * 32)

        # A first-time pin on a row that has no key still lands.
        mod.record_attestation_success("fresh-miner", device, True, "127.0.0.1", fingerprint={}, signing_pubkey=None)
        self.assertIsNone(self._pinned_key(db_path, "fresh-miner"))
        mod.record_attestation_success("fresh-miner", device, True, "127.0.0.1", fingerprint={}, signing_pubkey="cd" * 32)
        self.assertEqual(self._pinned_key(db_path, "fresh-miner"), "cd" * 32)


if __name__ == "__main__":
    unittest.main()
