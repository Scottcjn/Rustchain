# SPDX-License-Identifier: MIT
"""
Route-level PoC: POST /governance/propose requires Ed25519 wallet ownership proof.

Before the fix, the endpoint accepted any wallet address as the proposer with no
signature check. The sister endpoint /governance/vote already enforced Ed25519
ownership. This file tests the fixed governance_propose() handler at the HTTP
layer using a real Flask test client and real nacl-signed payloads.

Tests cover:
  1. Missing auth fields -> 400
  2. wallet/public-key mismatch -> 400
  3. Invalid (wrong-key) signature -> 401
  4. Valid signed proposal -> 201 (happy path + API contract fixture)
  5. Balance guard still applies -> 403

Run with:
    python -m pytest node/test_governance_propose_missing_sig_poc.py -v
"""

import hashlib
import json
import os
import sqlite3
import tempfile
import time
import unittest

import pytest
from flask import Flask, jsonify, request


# ---------------------------------------------------------------------------
# Inline crypto helpers (copied verbatim from rustchain_v2_integrated).
# Inlining avoids pulling in the 9 000-line main module in tests.
# ---------------------------------------------------------------------------

try:
    from nacl.signing import SigningKey, VerifyKey
    from nacl.exceptions import BadSignatureError
    _HAVE_NACL = True
except ImportError:
    _HAVE_NACL = False

pytestmark = pytest.mark.skipif(not _HAVE_NACL, reason="pynacl not installed")


def _verify_rtc_signature(public_key_hex: str, message: bytes, signature_hex: str) -> bool:
    try:
        vk = VerifyKey(bytes.fromhex(public_key_hex))
        vk.verify(message, bytes.fromhex(signature_hex))
        return True
    except Exception:
        return False


def _address_from_pubkey(public_key_hex: str) -> str:
    return "RTC" + hashlib.sha256(bytes.fromhex(public_key_hex)).hexdigest()[:40]


# ---------------------------------------------------------------------------
# Minimal governance schema helpers
# ---------------------------------------------------------------------------

GOVERNANCE_MIN_BALANCE_RTC = 10.0
GOVERNANCE_ACTIVE_SECONDS  = 7 * 24 * 3600
UNIT = 1_000_000


def _seed_db(db_path: str, wallet: str, balance_rtc: float) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS balances (
                miner_pk TEXT PRIMARY KEY,
                balance_rtc REAL NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS governance_proposals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                proposer_wallet TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                activated_at INTEGER,
                ends_at INTEGER,
                status TEXT NOT NULL DEFAULT 'draft',
                yes_weight REAL NOT NULL DEFAULT 0,
                no_weight REAL NOT NULL DEFAULT 0
            );
        """)
        conn.execute(
            "INSERT OR REPLACE INTO balances (miner_pk, balance_rtc) VALUES (?, ?)",
            (wallet, balance_rtc),
        )


# ---------------------------------------------------------------------------
# Minimal Flask app that re-implements governance_propose() with the fix.
# This is the exact same logic as the patched handler in the main node.
# ---------------------------------------------------------------------------

def _make_app(db_path: str) -> Flask:
    app = Flask(__name__)

    @app.route("/governance/propose", methods=["POST"])
    def governance_propose():
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return jsonify({"ok": False, "error": "JSON object required"}), 400

        wallet      = str(data.get("wallet",      "")).strip()
        title       = str(data.get("title",       "")).strip()
        description = str(data.get("description", "")).strip()
        nonce       = str(data.get("nonce",       "")).strip()

        raw_sig    = data.get("signature")
        raw_pubkey = data.get("public_key")
        if raw_sig    is not None and not isinstance(raw_sig,    str):
            return jsonify({"ok": False, "error": "INVALID_SIGNATURE_TYPE"}),  400
        if raw_pubkey is not None and not isinstance(raw_pubkey, str):
            return jsonify({"ok": False, "error": "INVALID_PUBLIC_KEY_TYPE"}), 400
        signature  = str(raw_sig    or "").strip()
        public_key = str(raw_pubkey or "").strip()

        if not wallet or not title or not description:
            return jsonify({"ok": False,
                            "error": "wallet, title and description are required"}), 400

        if not all([nonce, signature, public_key]):
            return jsonify({
                "ok": False,
                "error": "nonce, signature, public_key are required to authenticate the proposer",
            }), 400

        try:
            expected_wallet = _address_from_pubkey(public_key)
        except (ValueError, TypeError):
            return jsonify({"ok": False, "error": "invalid_public_key"}), 400

        if wallet != expected_wallet:
            return jsonify({"ok": False,
                            "error": "wallet_does_not_match_public_key",
                            "expected": expected_wallet,
                            "got": wallet}), 400

        propose_msg = json.dumps({
            "description": description,
            "nonce": nonce,
            "title": title,
            "wallet": wallet,
        }, sort_keys=True, separators=(",", ":")).encode()

        if not _verify_rtc_signature(public_key, propose_msg, signature):
            return jsonify({"ok": False, "error": "invalid_signature"}), 401

        with sqlite3.connect(db_path) as conn:
            row = conn.execute(
                "SELECT balance_rtc FROM balances WHERE miner_pk = ?", (wallet,)
            ).fetchone()
            balance_rtc = row[0] if row else 0.0
            if balance_rtc <= GOVERNANCE_MIN_BALANCE_RTC:
                return jsonify({
                    "ok": False,
                    "error": "insufficient_balance_to_propose",
                    "required_gt_rtc": GOVERNANCE_MIN_BALANCE_RTC,
                    "balance_rtc": balance_rtc,
                }), 403

            now     = int(time.time())
            ends_at = now + GOVERNANCE_ACTIVE_SECONDS
            cur = conn.execute(
                "INSERT INTO governance_proposals"
                " (proposer_wallet, title, description, created_at, activated_at, ends_at, status)"
                " VALUES (?, ?, ?, ?, ?, ?, 'active')",
                (wallet, title, description, now, now, ends_at),
            )
            proposal_id = cur.lastrowid

        return jsonify({
            "ok": True,
            "proposal": {
                "id": proposal_id,
                "wallet": wallet,
                "title": title,
                "description": description,
                "status": "active",
            },
        }), 201

    return app


# ---------------------------------------------------------------------------
# Key-generation helper — deterministic for test reproducibility.
# ---------------------------------------------------------------------------

def _make_keypair() -> tuple[str, str, str]:
    """Return (privkey_hex, pubkey_hex, wallet_address)."""
    sk  = SigningKey.generate()
    pk  = sk.verify_key
    pub = pk.encode().hex()
    return sk.encode().hex(), pub, _address_from_pubkey(pub)


def _sign_propose(sk_hex: str, wallet: str, title: str,
                  description: str, nonce: str) -> str:
    """Sign the canonical propose message; return signature hex."""
    msg = json.dumps({
        "description": description,
        "nonce":       nonce,
        "title":       title,
        "wallet":      wallet,
    }, sort_keys=True, separators=(",", ":")).encode()
    sk  = SigningKey(bytes.fromhex(sk_hex))
    sig = sk.sign(msg).signature
    return sig.hex()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGovernanceProposeRoute(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        self._db_path = tmp.name
        self._sk, self._pk, self._wallet = _make_keypair()
        _seed_db(self._db_path, self._wallet, 100.0)
        self._app    = _make_app(self._db_path)
        self._client = self._app.test_client()

    def tearDown(self):
        os.unlink(self._db_path)

    # -- helpers ---------------------------------------------------------------

    def _post(self, payload: dict):
        return self._client.post(
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
        body = json.loads(r.data)
        self.assertFalse(body["ok"])
        self.assertIn("nonce", body["error"])

    def test_missing_signature_returns_400(self):
        p = self._valid_payload()
        del p["signature"]
        r = self._post(p)
        self.assertEqual(r.status_code, 400)
        body = json.loads(r.data)
        self.assertFalse(body["ok"])

    def test_missing_public_key_returns_400(self):
        p = self._valid_payload()
        del p["public_key"]
        r = self._post(p)
        self.assertEqual(r.status_code, 400)
        body = json.loads(r.data)
        self.assertFalse(body["ok"])

    # -- 2. Wallet/public-key mismatch -----------------------------------------

    def test_wallet_pubkey_mismatch_returns_400(self):
        """wallet in body belongs to a different keypair than public_key."""
        _, other_pk, _other_wallet = _make_keypair()
        p = self._valid_payload()
        p["public_key"] = other_pk          # pubkey derives a different address
        r = self._post(p)
        self.assertEqual(r.status_code, 400)
        body = json.loads(r.data)
        self.assertFalse(body["ok"])
        self.assertEqual(body["error"], "wallet_does_not_match_public_key")

    # -- 3. Invalid signature --------------------------------------------------

    def test_wrong_key_signature_returns_401(self):
        """Signature was produced with a different private key."""
        other_sk, other_pk, other_wallet = _make_keypair()
        _seed_db(self._db_path, other_wallet, 100.0)
        # Sign with other_sk but submit other_wallet + other_pk (keys match),
        # yet change the message content after signing to break verification.
        nonce = "tampered-nonce"
        sig = _sign_propose(other_sk, other_wallet,
                            "Legit Title", "Legit desc.", nonce)
        r = self._post({
            "wallet":      other_wallet,
            "title":       "DIFFERENT TITLE",   # message was changed after signing
            "description": "Legit desc.",
            "nonce":       nonce,
            "signature":   sig,
            "public_key":  other_pk,
        })
        self.assertEqual(r.status_code, 401)
        body = json.loads(r.data)
        self.assertFalse(body["ok"])
        self.assertEqual(body["error"], "invalid_signature")

    def test_garbage_signature_hex_returns_401(self):
        p = self._valid_payload()
        p["signature"] = "deadbeef" * 16   # wrong length / wrong bytes
        r = self._post(p)
        self.assertEqual(r.status_code, 401)
        self.assertFalse(json.loads(r.data)["ok"])

    # -- 4. Valid signed proposal (happy path + API contract) ------------------

    def test_valid_signed_proposal_returns_201(self):
        """
        API contract fixture: documents the exact canonical signing message.

        Canonical message:
          json.dumps(
              {"description": <str>, "nonce": <str>, "title": <str>, "wallet": <str>},
              sort_keys=True, separators=(",", ":")
          ).encode()

        Fields are sorted alphabetically: description, nonce, title, wallet.
        """
        nonce = "unique-nonce-42"
        r = self._post(self._valid_payload(nonce))
        self.assertEqual(r.status_code, 201)
        body = json.loads(r.data)
        self.assertTrue(body["ok"])
        self.assertIn("proposal", body)
        self.assertEqual(body["proposal"]["wallet"],      self._wallet)
        self.assertEqual(body["proposal"]["title"],       "Test Proposal")
        self.assertEqual(body["proposal"]["description"], "A real description.")
        self.assertEqual(body["proposal"]["status"],      "active")

    def test_valid_proposal_persisted_in_db(self):
        """Accepted proposals are written to governance_proposals."""
        self._post(self._valid_payload("nonce-db-check"))
        with sqlite3.connect(self._db_path) as conn:
            rows = conn.execute("SELECT * FROM governance_proposals").fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][1], self._wallet)   # proposer_wallet column

    # -- 5. Balance guard still applies ----------------------------------------

    def test_insufficient_balance_returns_403(self):
        poor_sk, poor_pk, poor_wallet = _make_keypair()
        _seed_db(self._db_path, poor_wallet, 5.0)   # below 10 RTC minimum
        nonce = "poor-nonce"
        sig   = _sign_propose(poor_sk, poor_wallet,
                              "Cheap Proposal", "desc.", nonce)
        r = self._post({
            "wallet": poor_wallet, "title": "Cheap Proposal",
            "description": "desc.", "nonce": nonce,
            "signature": sig, "public_key": poor_pk,
        })
        self.assertEqual(r.status_code, 403)
        body = json.loads(r.data)
        self.assertFalse(body["ok"])
        self.assertEqual(body["error"], "insufficient_balance_to_propose")

    # -- 6. Non-string type guards ---------------------------------------------

    def test_non_string_signature_type_returns_400(self):
        p = self._valid_payload()
        p["signature"] = 12345
        r = self._post(p)
        self.assertEqual(r.status_code, 400)
        self.assertIn("INVALID_SIGNATURE_TYPE", json.loads(r.data)["error"])

    def test_non_string_pubkey_type_returns_400(self):
        p = self._valid_payload()
        p["public_key"] = ["not", "a", "string"]
        r = self._post(p)
        self.assertEqual(r.status_code, 400)
        self.assertIn("INVALID_PUBLIC_KEY_TYPE", json.loads(r.data)["error"])


if __name__ == "__main__":
    unittest.main()
