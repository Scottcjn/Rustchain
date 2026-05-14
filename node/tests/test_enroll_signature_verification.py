# SPDX-License-Identifier: MIT
"""
Tests for enrollment signature verification on /epoch/enroll.

Covers the fix for: /epoch/enroll lacks signature verification / ownership proof.
Without this fix, any caller who knows a pubkey with a recent attestation can enroll
it — including hijacking the miner_id mapping via INSERT OR REPLACE INTO miner_header_keys.

The fix requires Ed25519 signatures on enrollment requests, verified against the
signing pubkey stored during the miner's most recent attestation.
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
    "CREATE TABLE IF NOT EXISTS miner_attest_recent (miner TEXT PRIMARY KEY, ts_ok INTEGER NOT NULL, device_family TEXT, device_arch TEXT, entropy_score REAL DEFAULT 0, fingerprint_passed INTEGER DEFAULT 0, source_ip TEXT, warthog_bonus REAL DEFAULT 1.0, signing_pubkey TEXT)",
    "CREATE TABLE IF NOT EXISTS hardware_bindings (hardware_id TEXT PRIMARY KEY, bound_miner TEXT NOT NULL, device_arch TEXT, device_model TEXT, bound_at INTEGER NOT NULL, attestation_count INTEGER DEFAULT 0)",
    "CREATE TABLE IF NOT EXISTS miner_header_keys (miner_id TEXT PRIMARY KEY, pubkey_hex TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS miner_macs (miner TEXT NOT NULL, mac_hash TEXT NOT NULL, first_ts INTEGER NOT NULL, last_ts INTEGER NOT NULL, count INTEGER NOT NULL DEFAULT 1, PRIMARY KEY (miner, mac_hash))",
    "CREATE TABLE IF NOT EXISTS epoch_enroll (epoch INTEGER, miner_pk TEXT, weight REAL, PRIMARY KEY (epoch, miner_pk))",
    "CREATE TABLE IF NOT EXISTS balances (miner_pk TEXT PRIMARY KEY, balance_rtc REAL NOT NULL DEFAULT 0)",
    "CREATE TABLE IF NOT EXISTS tickets (ticket_id TEXT PRIMARY KEY, expires_at INTEGER, commitment TEXT)",
    "CREATE TABLE IF NOT EXISTS epoch_state (epoch INTEGER PRIMARY KEY, pot REAL, finalized INTEGER DEFAULT 0)",
]


def _sign_message(miner_id: str, wallet: str, nonce: str, commitment: str):
    """Sign an attestation message using Ed25519, return (signature_hex, public_key_hex)."""
    signing_key = nacl.signing.SigningKey.generate()
    verify_key = signing_key.verify_key
    pubkey_hex = verify_key.encode().hex()
    message = '{}|{}|{}|{}'.format(miner_id, wallet, nonce, commitment)
    signature = signing_key.sign(message.encode('utf-8'))
    return signature.signature.hex(), pubkey_hex, signing_key


def _sign_enrollment(miner_pk: str, miner_id: str, epoch: int, signing_key):
    """Sign an enrollment message using the given Ed25519 signing key."""
    verify_key = signing_key.verify_key
    pubkey_hex = verify_key.encode().hex()
    message = '{}|{}|{}'.format(miner_pk, miner_id, epoch)
    signature = signing_key.sign(message.encode('utf-8'))
    return signature.signature.hex(), pubkey_hex


class TestEnrollSignatureVerification(unittest.TestCase):
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

    def _submit_attestation(self, mod, payload):
        """Submit an attestation and return (status, body)."""
        with mod.app.test_request_context("/attest/submit", method="POST", json=payload):
            return self._response_payload(mod._submit_attestation_impl())

    def _enroll(self, mod, payload):
        """Enroll in epoch and return (status, body)."""
        with mod.app.test_request_context("/epoch/enroll", method="POST", json=payload):
            return self._response_payload(mod.enroll_epoch())

    def _attest_and_get_signing_key(self, mod, miner, miner_id):
        """Complete attestation flow and return the signing key used."""
        nonce = self._get_challenge(mod)
        commitment = "deadbeef"
        sig_hex, pubkey_hex, signing_key = _sign_message(miner_id, miner, nonce, commitment)

        payload = {
            "miner": miner,
            "miner_id": miner_id,
            "report": {"nonce": nonce, "commitment": commitment},
            "device": {"family": "PowerPC", "arch": "G4", "model": "test-box", "cores": 4},
            "signals": {"hostname": "test-host", "macs": []},
            "fingerprint": {},
            "signature": sig_hex,
            "public_key": pubkey_hex,
        }
        status, body = self._submit_attestation(mod, payload)
        self.assertEqual(status, 200, f"Attestation failed: {body}")
        return signing_key, pubkey_hex

    @unittest.skipUnless(HAVE_NACL, "pynacl not installed")
    def test_signed_enrollment_accepted(self):
        """A correctly signed enrollment should be accepted after attestation."""
        mod, db_path = self._load_module("rustchain_enroll_sig_valid", "enroll_sig_valid.db")

        miner = "RTC_VALID_MINER"
        miner_id = "miner_001"
        signing_key, pubkey_hex = self._attest_and_get_signing_key(mod, miner, miner_id)

        # Get current epoch
        with mod.app.test_request_context("/epoch", method="GET"):
            epoch_body = mod.get_epoch().get_json()
        epoch = epoch_body["epoch"]

        sig_hex, enroll_pubkey = _sign_enrollment(miner, miner_id, epoch, signing_key)

        payload = {
            "miner_pubkey": miner,
            "miner_id": miner_id,
            "device": {"family": "PowerPC", "arch": "G4"},
            "signature": sig_hex,
            "public_key": enroll_pubkey,
        }
        status, body = self._enroll(mod, payload)

        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])
        self.assertEqual(body["miner_pk"], miner)

    @unittest.skipUnless(HAVE_NACL, "pynacl not installed")
    def test_enrollment_with_wrong_key_rejected(self):
        """Enrollment signed with a different keypair than the attestation must be rejected."""
        mod, db_path = self._load_module("rustchain_enroll_sig_wrong_key", "enroll_sig_wrong_key.db")

        miner = "RTC_WRONG_KEY_MINER"
        miner_id = "miner_002"
        _, _ = self._attest_and_get_signing_key(mod, miner, miner_id)

        # Attacker uses their own keypair to sign enrollment
        attacker_key = nacl.signing.SigningKey.generate()

        with mod.app.test_request_context("/epoch", method="GET"):
            epoch_body = mod.get_epoch().get_json()
        epoch = epoch_body["epoch"]

        sig_hex, enroll_pubkey = _sign_enrollment(miner, miner_id, epoch, attacker_key)

        payload = {
            "miner_pubkey": miner,
            "miner_id": miner_id,
            "device": {"family": "x86_64", "arch": "default"},
            "signature": sig_hex,
            "public_key": enroll_pubkey,
        }
        status, body = self._enroll(mod, payload)

        self.assertEqual(status, 400)
        self.assertEqual(body["code"], "PUBKEY_MISMATCH")

    @unittest.skipUnless(HAVE_NACL, "pynacl not installed")
    def test_enrollment_with_invalid_signature_rejected(self):
        """Enrollment with a bogus signature must be rejected."""
        mod, db_path = self._load_module("rustchain_enroll_sig_invalid", "enroll_sig_invalid.db")

        miner = "RTC_INVALID_SIG_MINER"
        miner_id = "miner_003"
        _, attest_pubkey = self._attest_and_get_signing_key(mod, miner, miner_id)

        with mod.app.test_request_context("/epoch", method="GET"):
            epoch_body = mod.get_epoch().get_json()
        epoch = epoch_body["epoch"]

        payload = {
            "miner_pubkey": miner,
            "miner_id": miner_id,
            "device": {"family": "x86_64", "arch": "default"},
            "signature": "aa" * 64,  # Bogus signature
            "public_key": attest_pubkey,
        }
        status, body = self._enroll(mod, payload)

        self.assertEqual(status, 400)
        self.assertEqual(body["code"], "INVALID_ENROLLMENT_SIGNATURE")

    @unittest.skipUnless(HAVE_NACL, "pynacl not installed")
    def test_enrollment_with_tampered_message_rejected(self):
        """Enrollment with a valid signature but tampered miner_id must be rejected."""
        mod, db_path = self._load_module("rustchain_enroll_sig_tamper", "enroll_sig_tamper.db")

        miner = "RTC_TAMPER_MINER"
        miner_id = "miner_004"
        signing_key, attest_pubkey = self._attest_and_get_signing_key(mod, miner, miner_id)

        with mod.app.test_request_context("/epoch", method="GET"):
            epoch_body = mod.get_epoch().get_json()
        epoch = epoch_body["epoch"]

        # Sign with the correct miner_id
        sig_hex, enroll_pubkey = _sign_enrollment(miner, miner_id, epoch, signing_key)

        # But submit with a different miner_id
        payload = {
            "miner_pubkey": miner,
            "miner_id": "attacker_miner_id",
            "device": {"family": "x86_64", "arch": "default"},
            "signature": sig_hex,
            "public_key": enroll_pubkey,
        }
        status, body = self._enroll(mod, payload)

        self.assertEqual(status, 400)
        self.assertEqual(body["code"], "INVALID_ENROLLMENT_SIGNATURE")

    def test_unsigned_enrollment_rejected_after_attestation(self):
        """Unsigned enrollment must be rejected when miner has an attestation record.

        This is the fix for issue #5125: previously unsigned enrollment was accepted
        for all miners (warn-only), allowing anyone to impersonate an attested miner
        by enrolling without proving key ownership. The fix requires signed enrollment
        once a miner has attested.
        """
        mod, db_path = self._load_module("rustchain_enroll_signed_required", "enroll_signed_required.db")

        miner = "RTC_SIGNED_REQUIRED_MINER"
        miner_id = "miner_005"

        # Attest (creates miner_attest_recent record)
        nonce = self._get_challenge(mod)
        payload = {
            "miner": miner,
            "miner_id": miner_id,
            "report": {"nonce": nonce, "commitment": "deadbeef"},
            "device": {"family": "x86_64", "arch": "default", "model": "test-box", "cores": 4},
            "signals": {"hostname": "test-host", "macs": []},
            "fingerprint": {},
        }
        status, body = self._submit_attestation(mod, payload)
        self.assertEqual(status, 200)

        # Enroll without signature — should be rejected
        payload = {
            "miner_pubkey": miner,
            "miner_id": miner_id,
            "device": {"family": "x86_64", "arch": "default"},
        }
        status, body = self._enroll(mod, payload)

        # Must be rejected — miner has attestation record
        self.assertEqual(status, 400)
        self.assertEqual(body["code"], "UNSIGNED_ENROLLMENT_REJECTED")

    def test_unsigned_enrollment_legacy_rejected_by_attestation_requirement(self):
        """Miners with NO attestation are rejected by check_enrollment_requirements.

        This is expected: ENROLL_REQUIRE_TICKET blocks non-attested miners before
        the unsigned/signature check is even reached. The legacy unsigned path
        only exists as defense-in-depth code but is unreachable in production.
        """
        mod, db_path = self._load_module("rustchain_enroll_legacy", "enroll_legacy.db")

        miner = "RTC_LEGACY_MINER"
        miner_id = "miner_legacy_001"

        # Do NOT attest — go straight to enrollment
        payload = {
            "miner_pubkey": miner,
            "miner_id": miner_id,
            "device": {"family": "x86_64", "arch": "default"},
        }
        status, body = self._enroll(mod, payload)

        # Rejected by check_enrollment_requirements (no recent attestation)
        self.assertEqual(status, 412)
        self.assertEqual(body["error"], "no_recent_attestation")

    @unittest.skipUnless(HAVE_NACL, "pynacl not installed")
    def test_enrollment_with_incomplete_signature_rejected(self):
        """Enrollment with only signature or only public_key must be rejected."""
        mod, db_path = self._load_module("rustchain_enroll_sig_incomplete", "enroll_sig_incomplete.db")

        miner = "RTC_INCOMPLETE_MINER"
        miner_id = "miner_006"
        signing_key, attest_pubkey = self._attest_and_get_signing_key(mod, miner, miner_id)

        with mod.app.test_request_context("/epoch", method="GET"):
            epoch_body = mod.get_epoch().get_json()
        epoch = epoch_body["epoch"]

        sig_hex, _ = _sign_enrollment(miner, miner_id, epoch, signing_key)

        # Only signature, no public_key
        payload = {
            "miner_pubkey": miner,
            "miner_id": miner_id,
            "device": {"family": "x86_64", "arch": "default"},
            "signature": sig_hex,
        }
        status, body = self._enroll(mod, payload)
        self.assertEqual(status, 400)
        self.assertEqual(body["code"], "INCOMPLETE_SIGNATURE")

        # Only public_key, no signature
        payload = {
            "miner_pubkey": miner,
            "miner_id": miner_id,
            "device": {"family": "x86_64", "arch": "default"},
            "public_key": attest_pubkey,
        }
        status, body = self._enroll(mod, payload)
        self.assertEqual(status, 400)
        self.assertEqual(body["code"], "INCOMPLETE_SIGNATURE")

    @unittest.skipUnless(HAVE_NACL, "pynacl not installed")
    def test_enrollment_pubkey_mismatch_with_attacker_key(self):
        """Attacker cannot enroll victim's pubkey using attacker's signing key."""
        mod, db_path = self._load_module("rustchain_enroll_hijack", "enroll_hijack.db")

        victim = "RTC_VICTIM"
        victim_id = "victim_001"
        _, _ = self._attest_and_get_signing_key(mod, victim, victim_id)

        # Attacker generates their own keypair
        attacker_key = nacl.signing.SigningKey.generate()
        attacker_pubkey = attacker_key.verify_key.encode().hex()

        with mod.app.test_request_context("/epoch", method="GET"):
            epoch_body = mod.get_epoch().get_json()
        epoch = epoch_body["epoch"]

        # Attacker signs victim's pubkey with attacker's key
        sig_hex, _ = _sign_enrollment(victim, victim_id, epoch, attacker_key)

        payload = {
            "miner_pubkey": victim,
            "miner_id": victim_id,
            "device": {"family": "x86_64", "arch": "default"},
            "signature": sig_hex,
            "public_key": attacker_pubkey,
        }
        status, body = self._enroll(mod, payload)

        # Must be rejected — attacker's pubkey doesn't match victim's attestation
        self.assertEqual(status, 400)
        self.assertEqual(body["code"], "PUBKEY_MISMATCH")


if __name__ == "__main__":
    unittest.main()
