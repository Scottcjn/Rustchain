# SPDX-License-Identifier: MIT
"""
Route-level PoC: POST /governance/propose requires Ed25519 wallet ownership proof.

Tests the real governance_propose() handler in rustchain_v2_integrated_v2.2.1_rip200.py
using a real Flask test client, a temp SQLite database, and real nacl-signed payloads.

Covers:
  1. Missing auth fields -> 400
  2. wallet/public-key mismatch -> 400
  3. Invalid (wrong-key) signature -> 401
  4. Valid signed proposal -> 201 (happy path + API contract fixture)
  5. Balance guard still applies -> 403
  6. Non-string field type guards -> 400
"""

import gc
import hashlib
import importlib.util as _ilu
import json
import os
import sqlite3
import sys
import tempfile
import unittest

import pytest

sys.path.insert(0, os.path.dirname(__file__))

try:
    from nacl.signing import SigningKey, VerifyKey  # noqa: F401
    from nacl.exceptions import BadSignatureError   # noqa: F401
    _HAVE_NACL = True
except ImportError:
    _HAVE_NACL = False

pytestmark = pytest.mark.skipif(not _HAVE_NACL, reason="pynacl not installed")

# ---------------------------------------------------------------------------
# Load the real app once at module level.
# Set RUSTCHAIN_DB_PATH before loading so DB_PATH is initialised to our file.
# ---------------------------------------------------------------------------

_module_db_fd, _MODULE_DB = tempfile.mkstemp(suffix=".db")
os.close(_module_db_fd)

os.environ.setdefault("RC_ADMIN_KEY", "0123456789abcdef0123456789abcdef")
os.environ["RUSTCHAIN_DB_PATH"] = _MODULE_DB

_spec = _ilu.spec_from_file_location(
    "rustchain_node",
    os.path.join(os.path.dirname(__file__), "rustchain_v2_integrated_v2.2.1_rip200.py"),
)
_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
_app = _mod.app


# ---------------------------------------------------------------------------
# Crypto helpers
# ---------------------------------------------------------------------------

def _address_from_pubkey(public_key_hex: str) -> str:
    return "RTC" + hashlib.sha256(bytes.fromhex(public_key_hex)).hexdigest()[:40]


def _make_keypair() -> tuple[str, str, str]:
    sk  = SigningKey.generate()
    pub = sk.verify_key.encode().hex()
    return sk.encode().hex(), pub, _address_from_pubkey(pub)


def _sign_propose(sk_hex: str, wallet: str, title: str, description: str, nonce: str) -> str:
    msg = json.dumps({
        "description": description,
        "nonce":       nonce,
        "title":       title,
        "wallet":      wallet,
    }, sort_keys=True, separators=(",", ":")).encode()
    sk  = SigningKey(bytes.fromhex(sk_hex))
    return sk.sign(msg).signature.hex()


# ---------------------------------------------------------------------------
# DB seeding — uses the schema expected by _balance_i64_for_wallet()
# ---------------------------------------------------------------------------

_BALANCE_ABOVE_MIN = int(100 * 1_000_000)   # 100 RTC in micro-units
_BALANCE_BELOW_MIN = int(5   * 1_000_000)   # 5 RTC — below 10 RTC minimum


def _seed_db(db_path: str, wallet: str, amount_i64: int) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS balances (
                miner_id TEXT PRIMARY KEY,
                amount_i64 INTEGER NOT NULL DEFAULT 0
            );
        """)
        conn.execute(
            "INSERT OR REPLACE INTO balances (miner_id, amount_i64) VALUES (?, ?)",
            (wallet, amount_i64),
        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------

class TestGovernanceProposeRealRoute(unittest.TestCase):

    def setUp(self):
        fd, self._db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self._sk, self._pk, self._wallet = _make_keypair()
        _seed_db(self._db_path, self._wallet, _BALANCE_ABOVE_MIN)
        _mod.DB_PATH = self._db_path
        _app.config["TESTING"] = True
        self.client = _app.test_client()

    def tearDown(self):
        _mod.DB_PATH = _MODULE_DB   # restore so other tests are not affected
        gc.collect()                # release any sqlite3.Connection objects held by the route
        try:
            os.unlink(self._db_path)
        except PermissionError:
            pass   # Windows: OS will clean up on process exit

    # -- helpers ---------------------------------------------------------------

    def _post(self, payload: dict):
        return self.client.post(
            "/governance/propose",
            data=json.dumps(payload),
            content_type="application/json",
        )

    def _valid_payload(self, nonce: str = "test-nonce-1") -> dict:
        sig = _sign_propose(self._sk, self._wallet,
                            "Test Proposal", "A real description.", nonce)
        return {
            "wallet":      self._wallet,
            "title":       "Test Proposal",
            "description": "A real description.",
            "nonce":       nonce,
            "signature":   sig,
            "public_key":  self._pk,
        }

    # -- 1. Missing auth fields ------------------------------------------------

    def test_missing_nonce_returns_400(self):
        p = self._valid_payload()
        del p["nonce"]
        r = self._post(p)
        self.assertEqual(r.status_code, 400)
        body = r.get_json()
        self.assertFalse(body["ok"])
        self.assertIn("nonce", body["error"])

    def test_missing_signature_returns_400(self):
        p = self._valid_payload()
        del p["signature"]
        r = self._post(p)
        self.assertEqual(r.status_code, 400)
        self.assertFalse(r.get_json()["ok"])

    def test_missing_public_key_returns_400(self):
        p = self._valid_payload()
        del p["public_key"]
        r = self._post(p)
        self.assertEqual(r.status_code, 400)
        self.assertFalse(r.get_json()["ok"])

    def test_missing_wallet_returns_400(self):
        p = self._valid_payload()
        del p["wallet"]
        r = self._post(p)
        self.assertEqual(r.status_code, 400)
        self.assertFalse(r.get_json()["ok"])

    # -- 2. Wallet/public-key mismatch -----------------------------------------

    def test_wallet_pubkey_mismatch_returns_400(self):
        _, other_pk, _ = _make_keypair()
        p = self._valid_payload()
        p["public_key"] = other_pk
        r = self._post(p)
        self.assertEqual(r.status_code, 400)
        body = r.get_json()
        self.assertFalse(body["ok"])
        self.assertEqual(body["error"], "wallet_does_not_match_public_key")

    # -- 3. Invalid signature --------------------------------------------------

    def test_wrong_key_signature_returns_401(self):
        other_sk, other_pk, other_wallet = _make_keypair()
        _seed_db(self._db_path, other_wallet, _BALANCE_ABOVE_MIN)
        nonce = "tampered-nonce"
        sig = _sign_propose(other_sk, other_wallet, "Legit Title", "Legit desc.", nonce)
        r = self._post({
            "wallet":      other_wallet,
            "title":       "DIFFERENT TITLE",
            "description": "Legit desc.",
            "nonce":       nonce,
            "signature":   sig,
            "public_key":  other_pk,
        })
        self.assertEqual(r.status_code, 401)
        body = r.get_json()
        self.assertFalse(body["ok"])
        self.assertEqual(body["error"], "invalid_signature")

    def test_garbage_signature_hex_returns_401(self):
        p = self._valid_payload()
        p["signature"] = "deadbeef" * 16
        r = self._post(p)
        self.assertEqual(r.status_code, 401)
        self.assertFalse(r.get_json()["ok"])

    # -- 4. Valid signed proposal (happy path + API contract) ------------------

    def test_valid_signed_proposal_returns_201(self):
        r = self._post(self._valid_payload("unique-nonce-42"))
        self.assertEqual(r.status_code, 201)
        body = r.get_json()
        self.assertTrue(body["ok"])
        prop = body["proposal"]
        self.assertEqual(prop["wallet"],      self._wallet)
        self.assertEqual(prop["title"],       "Test Proposal")
        self.assertEqual(prop["description"], "A real description.")
        self.assertEqual(prop["status"],      "active")

    def test_valid_proposal_persisted_in_db(self):
        self._post(self._valid_payload("nonce-db-check"))
        conn = sqlite3.connect(self._db_path)
        try:
            rows = conn.execute("SELECT proposer_wallet FROM governance_proposals").fetchall()
        finally:
            conn.close()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], self._wallet)

    # -- 5. Balance guard still applies ----------------------------------------

    def test_insufficient_balance_returns_403(self):
        poor_sk, poor_pk, poor_wallet = _make_keypair()
        _seed_db(self._db_path, poor_wallet, _BALANCE_BELOW_MIN)
        nonce = "poor-nonce"
        sig   = _sign_propose(poor_sk, poor_wallet, "Cheap Proposal", "desc.", nonce)
        r = self._post({
            "wallet": poor_wallet, "title": "Cheap Proposal",
            "description": "desc.", "nonce": nonce,
            "signature": sig, "public_key": poor_pk,
        })
        self.assertEqual(r.status_code, 403)
        body = r.get_json()
        self.assertFalse(body["ok"])
        self.assertEqual(body["error"], "insufficient_balance_to_propose")

    # -- 6. Non-string type guards ---------------------------------------------

    def test_non_string_signature_type_returns_400(self):
        p = self._valid_payload()
        p["signature"] = 12345
        r = self._post(p)
        self.assertEqual(r.status_code, 400)
        self.assertIn("INVALID_SIGNATURE_TYPE", r.get_json()["error"])

    def test_non_string_pubkey_type_returns_400(self):
        p = self._valid_payload()
        p["public_key"] = ["not", "a", "string"]
        r = self._post(p)
        self.assertEqual(r.status_code, 400)
        self.assertIn("INVALID_PUBLIC_KEY_TYPE", r.get_json()["error"])


if __name__ == "__main__":
    unittest.main()
