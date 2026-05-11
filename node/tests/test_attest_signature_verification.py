# SPDX-License-Identifier: MIT
"""
Tests for attestation report signature verification.

Covers the fix for: server-side Ed25519 signature verification on /attest/submit.
The rustchain-miner signs (miner_id|wallet|nonce|commitment) but the node previously
never verified this signature, allowing wallet hijack via field modification in transit.
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
except Exception:
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


def _sign_message(miner_id: str, wallet: str, nonce: str, commitment: str):
    """Sign a message using Ed25519, return (signature_hex, public_key_hex)."""
    signing_key = nacl.signing.SigningKey.generate()
    verify_key = signing_key.verify_key
    pubkey_hex = verify_key.encode().hex()
    message = '{}|{}|{}|{}'.format(miner_id, wallet, nonce, commitment)
    signature = signing_key.sign(message.encode('utf-8'))
    return signature.signature.hex(), pubkey_hex


class TestAttestSignatureVerification(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls._prev_admin_key = os.environ.get("RC_ADMIN_KEY")
        cls._prev_db_path = os.environ.get("RUSTCHAIN_DB_PATH")
        os.environ["RC_ADMIN_KEY"] = "0123456789abcdef0123456789abcdef"

        if NODE_DIR not in sys.path:
            sys.path.insert(0, NODE_DIR)

    @classmethod
    def tearDownClass(cls):
        if cls._prev_admin_key is None:
            os.environ.pop("RC_ADMIN_KEY", None)
        else:
            os.environ["RC_ADMIN_KEY"] = cls._prev_admin_key
        if cls._prev_db_path is None:
            os.environ.pop("RUSTCHAIN_DB_PATH", None)
        else:
            os.environ["RUSTCHAIN_DB_PATH"] = cls._prev_db_path
        cls._tmp.cleanup()

    def _db_path(self, name: str) -> str:
        return str(Path(self._tmp.name) / name)

    def _load_module(self, module_name: str, db_name: str):
        db_path = self._db_path(db_name)
        os.environ["RUSTCHAIN_DB_PATH"] = db_path
        spec = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.init_db()
        with sqlite3.connect(db_path) as conn:
            for stmt in EXTRA_SCHEMA:
                conn.execute(stmt)
            conn.commit()
        return mod, db_path

    def _load_module_without_db(self, module_name: str, db_name: str):
        """Load the route module for pre-DB validation tests."""
        db_path = self._db_path(db_name)
        os.environ["RUSTCHAIN_DB_PATH"] = db_path
        spec = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod, db_path

    def _response_payload(self, resp):
        if isinstance(resp, tuple):
            body, status = resp
            return status, body.get_json()
        return resp.status_code, resp.get_json()

    def _get_challenge(self, mod):
        """Get a valid challenge nonce from the node."""
        with mod.app.test_request_context("/attest/challenge", method="POST", json={}):
            resp = mod.get_challenge()
        return resp.get_json()["nonce"]

    def _submit(self, mod, payload):
        with mod.app.test_request_context("/attest/submit", method="POST", json=payload):
            return self._response_payload(mod._submit_attestation_impl())

    def _submit_route(self, mod, payload):
        with mod.app.test_request_context("/attest/submit", method="POST", json=payload):
            return self._response_payload(mod.submit_attestation())

    def _base_payload(self, miner, nonce, commitment="deadbeef", sig_hex=None, pubkey_hex=None, miner_id=None):
        """Build a minimal valid attestation payload."""
        payload = {
            "miner": miner,
            "report": {"nonce": nonce, "commitment": commitment},
            "device": {"family": "x86_64", "arch": "default", "model": "test-box", "cores": 4},
            "signals": {"hostname": "test-host", "macs": []},
            "fingerprint": {},
        }
        if sig_hex is not None:
            payload["signature"] = sig_hex
        if pubkey_hex is not None:
            payload["public_key"] = pubkey_hex
        if miner_id is not None:
            payload["miner_id"] = miner_id
        return payload

    @unittest.skipUnless(HAVE_NACL, "pynacl not installed")
    def test_valid_signature_accepted(self):
        """A correctly signed attestation report should be accepted."""
        mod, _ = self._load_module("rustchain_attest_sig_valid", "sig_valid.db")

        miner = "RTC_VALID_MINER"
        miner_id = "miner_001"
        nonce = self._get_challenge(mod)
        commitment = "deadbeef"
        sig_hex, pubkey_hex = _sign_message(miner_id, miner, nonce, commitment)

        payload = self._base_payload(miner, nonce, commitment, sig_hex, pubkey_hex, miner_id)
        status, body = self._submit(mod, payload)

        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])

    @unittest.skipUnless(HAVE_NACL, "pynacl not installed")
    def test_tampered_wallet_rejected(self):
        """Changing the miner (wallet) field while keeping the original signature must be rejected."""
        mod, _ = self._load_module("rustchain_attest_sig_tamper", "sig_tamper.db")

        original_miner = "RTC_LEGITIMATE_MINER"
        attacker_miner = "RTC_ATTACKER_MINER"
        miner_id = "miner_001"
        nonce = self._get_challenge(mod)
        commitment = "cafebabe"

        # Sign with the original (legitimate) wallet
        sig_hex, pubkey_hex = _sign_message(miner_id, original_miner, nonce, commitment)

        # Attacker changes the miner field to their own wallet
        payload = self._base_payload(attacker_miner, nonce, commitment, sig_hex, pubkey_hex, miner_id)
        status, body = self._submit(mod, payload)

        self.assertEqual(status, 400)
        self.assertEqual(body["code"], "INVALID_SIGNATURE")
        self.assertEqual(body["error"], "invalid_attestation_signature")

    @unittest.skipUnless(HAVE_NACL, "pynacl not installed")
    def test_invalid_signature_rejected(self):
        """A payload with a bogus signature must be rejected."""
        mod, _ = self._load_module("rustchain_attest_sig_invalid", "sig_invalid.db")

        miner = "RTC_SOME_MINER"
        nonce = self._get_challenge(mod)
        commitment = "feedface"
        fake_sig = "00" * 64  # 64 bytes of zeros — not a valid Ed25519 signature
        fake_pubkey = "00" * 32  # 32 bytes of zeros — not a valid public key

        payload = self._base_payload(miner, nonce, commitment, fake_sig, fake_pubkey)
        status, body = self._submit(mod, payload)

        self.assertEqual(status, 400)
        self.assertEqual(body["code"], "INVALID_SIGNATURE")

    @unittest.skipUnless(HAVE_NACL, "pynacl not installed")
    def test_tampered_nonce_rejected(self):
        """Changing the nonce field while keeping the original signature must be rejected."""
        mod, _ = self._load_module("rustchain_attest_sig_nonce_tamper", "sig_nonce_tamper.db")

        miner = "RTC_MINER"
        miner_id = "miner_002"
        server_nonce = self._get_challenge(mod)
        tampered_nonce = "e" * 64  # different from server nonce
        commitment = "beefcafe"

        sig_hex, pubkey_hex = _sign_message(miner_id, miner, server_nonce, commitment)

        # Attacker changes the nonce in the report
        payload = self._base_payload(miner, tampered_nonce, commitment, sig_hex, pubkey_hex, miner_id)
        status, body = self._submit(mod, payload)

        self.assertEqual(status, 400)
        self.assertEqual(body["code"], "INVALID_SIGNATURE")

    @unittest.skipUnless(HAVE_NACL, "pynacl not installed")
    def test_tampered_commitment_rejected(self):
        """Changing the commitment field while keeping the original signature must be rejected."""
        mod, _ = self._load_module("rustchain_attest_sig_commit_tamper", "sig_commit_tamper.db")

        miner = "RTC_MINER"
        miner_id = "miner_003"
        nonce = self._get_challenge(mod)
        original_commitment = "deadbeef"
        tampered_commitment = "attacker00"

        sig_hex, pubkey_hex = _sign_message(miner_id, miner, nonce, original_commitment)

        payload = self._base_payload(miner, nonce, tampered_commitment, sig_hex, pubkey_hex, miner_id)
        status, body = self._submit(mod, payload)

        self.assertEqual(status, 400)
        self.assertEqual(body["code"], "INVALID_SIGNATURE")

    def test_missing_signature_allowed(self):
        """Backward compatibility: submissions without signature should still be accepted.

        This allows the simpler miner path (miners/rust/src/main.rs) to continue
        working while operators migrate to the signed attestation flow.
        """
        mod, _ = self._load_module("rustchain_attest_sig_missing", "sig_missing.db")

        nonce = self._get_challenge(mod)

        payload = {
            "miner": "RTC_UNSIGNED_MINER",
            "report": {"nonce": nonce, "commitment": "deadbeef"},
            "device": {"family": "x86_64", "arch": "default", "model": "test-box", "cores": 4},
            "signals": {"hostname": "test-host", "macs": []},
            "fingerprint": {},
        }
        status, body = self._submit(mod, payload)

        # Should succeed — no signature provided, so no verification attempted
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])

    def test_non_string_signature_rejected_before_handler_crash(self):
        """Non-string signature values must be validation failures, not 500s."""
        mod, _ = self._load_module_without_db("rustchain_attest_sig_type_guard", "sig_type_guard.db")

        payload = self._base_payload(
            miner="RTC_SIG_TYPE_MINER",
            nonce="not-a-live-challenge",
            sig_hex=12345,
            pubkey_hex="00" * 32,
        )
        status, body = self._submit_route(mod, payload)

        self.assertEqual(status, 400)
        self.assertEqual(body["code"], "INVALID_SIGNATURE_TYPE")

    def test_non_string_public_key_rejected_before_handler_crash(self):
        """Non-string public_key values must be validation failures, not 500s."""
        mod, _ = self._load_module_without_db("rustchain_attest_pubkey_type_guard", "pubkey_type_guard.db")

        payload = self._base_payload(
            miner="RTC_PUBKEY_TYPE_MINER",
            nonce="not-a-live-challenge",
            sig_hex="00" * 64,
            pubkey_hex=["not", "a", "key"],
        )
        status, body = self._submit_route(mod, payload)

        self.assertEqual(status, 400)
        self.assertEqual(body["code"], "INVALID_PUBLIC_KEY_TYPE")

    def test_signature_rejected_when_pynacl_missing(self):
        """When pynacl is not installed and a signature is provided, reject with 503.

        This is the fail-closed path: the node must not accept a signed
        attestation it cannot verify.  Unsigned attestations are still
        accepted for backward compatibility.

        We simulate HAVE_NACL=False by monkeypatching the module-level flag.
        """
        mod, _ = self._load_module(
            "rustchain_attest_sig_no_nacl", "sig_no_nacl.db",
        )
        # Monkeypatch HAVE_NACL to False to simulate missing pynacl
        original_have_nacl = mod.HAVE_NACL
        mod.HAVE_NACL = False

        nonce = self._get_challenge(mod)
        # Provide a signature — the node cannot verify it without pynacl
        payload = self._base_payload(
            "RTC_NO_NACL_MINER",
            nonce,
            "deadbeef",
            sig_hex="aa" * 64,
            pubkey_hex="bb" * 32,
            miner_id="miner_nacl_missing",
        )
        status, body = self._submit(mod, payload)

        # Must be rejected — fail-closed, not fail-open
        self.assertEqual(status, 503)
        self.assertEqual(body["code"], "ED25519_UNAVAILABLE")
        self.assertEqual(body["error"], "ed25519_unavailable")

        # Restore original flag (cleanup — module will be discarded anyway)
        mod.HAVE_NACL = original_have_nacl


if __name__ == "__main__":
    unittest.main()
