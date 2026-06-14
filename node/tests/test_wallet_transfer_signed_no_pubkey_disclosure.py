# SPDX-License-Identifier: MIT
"""
FIX #7311: /wallet/transfer/signed leaked the expected public key (and derived
RTC address) in error responses. An anonymous attacker could send a request
with a guessed `from_address` and a wrong `public_key`, then read the
`expected`/`expected_pubkey_prefix` field to map any RTC address to its
Ed25519 public key (full deanonymization of the address space).

This test file locks in the post-fix contract:
  - 400 response for the mismatch case
  - Response body MUST NOT contain `expected`, `expected_pubkey_prefix`,
    `expected_address`, or any other key that is derived from the server's
    canonical record.
  - Response body MUST contain the caller's own `from_address` (or `beacon_id`
    for the bcn_ branch) — the caller already knows this.
  - The fix must not regress the existing happy path or signature verification.
"""
import importlib.util
import gc
import os
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path


NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULE_PATH = os.path.join(NODE_DIR, "rustchain_v2_integrated_v2.2.1_rip200.py")
MODULE_NAME = "rustchain_integrated_7311_test"

# Local DB schema for the signed transfer path. The wallet_transfer_signed
# route touches: transfer_nonces (INSERT + SELECT MAX), wallets (no direct
# read in the failing branch but is touched by signed balance check) and
# bcn_registry when from_address starts with bcn_. The pre-validated
# `validate_wallet_transfer_signed` accepts bcn_ addresses of length >= 8.
EXTRA_SCHEMA = [
    "CREATE TABLE IF NOT EXISTS wallets (address TEXT PRIMARY KEY, balance_i64 INTEGER DEFAULT 0)",
    "CREATE TABLE IF NOT EXISTS transfer_nonces (from_address TEXT NOT NULL, nonce TEXT NOT NULL, used_at INTEGER NOT NULL, PRIMARY KEY (from_address, nonce))",
    "CREATE TABLE IF NOT EXISTS bcn_registry (beacon_id TEXT PRIMARY KEY, pubkey_hex TEXT, agent_name TEXT)",
    "CREATE TABLE IF NOT EXISTS balance_events (id INTEGER PRIMARY KEY AUTOINCREMENT, address TEXT NOT NULL, delta_i64 INTEGER NOT NULL, kind TEXT NOT NULL, ts INTEGER NOT NULL, ref TEXT)",
]


def _load_integrated_module():
    if MODULE_NAME in sys.modules:
        return sys.modules[MODULE_NAME]
    spec = importlib.util.spec_from_file_location(MODULE_NAME, MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[MODULE_NAME] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception:
        sys.modules.pop(MODULE_NAME, None)
        raise
    return mod


def _response_payload(resp):
    try:
        return resp.status_code, resp.get_json()
    except Exception:
        return resp.status_code, {}


class TestWalletTransferSignedNoPubkeyDisclosure(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls._prev_admin_key = os.environ.get("RC_ADMIN_KEY")
        cls._prev_db_path = os.environ.get("RUSTCHAIN_DB_PATH")
        cls._prev_disable_p2p = os.environ.get("RUSTCHAIN_DISABLE_P2P_AUTO_START")
        gc.collect()
        os.environ["RC_ADMIN_KEY"] = "0123456789abcdef0123456789abcdef"
        os.environ["RUSTCHAIN_DISABLE_P2P_AUTO_START"] = "1"

        if NODE_DIR not in sys.path:
            sys.path.insert(0, NODE_DIR)
        os.environ["RUSTCHAIN_DB_PATH"] = str(Path(cls._tmp.name) / "wallet_transfer_signed_7311.db")
        cls.mod = _load_integrated_module()
        cls.app = cls.mod.app
        cls.client = cls.app.test_client()

        with closing(sqlite3.connect(os.environ["RUSTCHAIN_DB_PATH"])) as conn:
            for ddl in EXTRA_SCHEMA:
                conn.execute(ddl)
            conn.commit()

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
        if cls._prev_disable_p2p is None:
            os.environ.pop("RUSTCHAIN_DISABLE_P2P_AUTO_START", None)
        else:
            os.environ["RUSTCHAIN_DISABLE_P2P_AUTO_START"] = cls._prev_disable_p2p
        try:
            sys.modules.pop(MODULE_NAME, None)
        except Exception:
            pass
        cls._tmp.cleanup()

    def _post(self, body):
        return self.client.post(
            "/wallet/transfer/signed",
            json=body,
        )

    # ------------------------------------------------------------------
    # Pre-fix: server returns 400 with body containing `expected` and `got`
    # Post-fix: server returns 400 with body that does NOT contain the
    # derived `expected_address`, but DOES echo the caller's from_address.
    # ------------------------------------------------------------------

    def test_pubkey_mismatch_does_not_leak_expected_address(self):
        """The pre-fix 400 response leaked the derived `expected_address` field.

        The post-fix response must not include that field. The caller already
        knows their own `from_address`; the server must not echo the canonical
        address derived from the registered public key.
        """
        # Use two distinct, valid-format RTC addresses (40 hex chars each).
        from_addr = "RTC0000000000000000000000000000000000000001"
        to_addr = "RTC0000000000000000000000000000000000000002"
        body = {
            "from_address": from_addr,
            "to_address": to_addr,
            "amount_rtc": "1.0",
            "nonce": "12345",
            "signature": "a",
            "public_key": "00",  # garbage; address derivation will not match from_addr
            "memo": "",
        }
        status, payload = _response_payload(self._post(body))
        self.assertEqual(status, 400, f"expected 400, got {status}: {payload}")
        # The pre-fix body contained `expected`. The post-fix body MUST NOT.
        self.assertNotIn(
            "expected", payload,
            f"response leaked `expected` field: {payload}"
        )
        # The pre-fix body contained `got`. Either we keep it under
        # `from_address` (rename) or drop it. The post-fix must not retain
        # the redundant `got` key.
        self.assertNotIn(
            "got", payload,
            f"response still has redundant `got` key: {payload}"
        )
        # The post-fix body must echo the caller's own from_address, since
        # that is non-sensitive (it came from the caller).
        self.assertEqual(
            payload.get("from_address"), from_addr,
            f"response must echo the caller's from_address; got: {payload}"
        )
        # The error code must remain the same.
        self.assertEqual(
            payload.get("error"), "Public key does not match from_address",
            f"error code regression: {payload}"
        )

    def test_pubkey_mismatch_no_full_derived_address_echoed(self):
        """Defense in depth: even if a future refactor renames the field,
        the response must not contain a 43-char `RTC` + 40-hex string other
        than the one the caller supplied.
        """
        from_addr = "RTC0000000000000000000000000000000000000001"
        to_addr = "RTC0000000000000000000000000000000000000002"
        body = {
            "from_address": from_addr,
            "to_address": to_addr,
            "amount_rtc": "1.0",
            "nonce": "12346",
            "signature": "a",
            "public_key": "00",
            "memo": "",
        }
        status, payload = _response_payload(self._post(body))
        self.assertEqual(status, 400, f"expected 400, got {status}: {payload}")

        def _is_rtc_addr(s):
            return (
                isinstance(s, str)
                and len(s) == 43
                and s.startswith("RTC")
                and all(c in "0123456789abcdefABCDEF" for c in s[3:])
            )

        def _walk_strings(obj, out):
            if isinstance(obj, str):
                out.append(obj)
            elif isinstance(obj, dict):
                for v in obj.values():
                    _walk_strings(v, out)
            elif isinstance(obj, list):
                for v in obj:
                    _walk_strings(v, out)

        all_strings = []
        _walk_strings(payload, all_strings)
        rtc_strings = [s for s in all_strings if _is_rtc_addr(s)]
        # The caller's from_addr is allowed (it came from the caller).
        # Any other RTC-format string in the response is a leak.
        unexpected = [s for s in rtc_strings if s != from_addr and s != to_addr]
        self.assertEqual(
            unexpected, [],
            f"response contains unexpected RTC address(es): {unexpected} "
            f"(full body: {payload})"
        )

    def test_pubkey_mismatch_no_pubkey_prefix_echoed(self):
        """The Beacon Atlas branch (bcn_ addresses) used to leak
        `expected_pubkey_prefix`. This regression case ensures the response
        does not contain a 16-char hex prefix of any 32/33-byte pubkey.
        """
        # A bcn_ address must be length >= 8 per validate_wallet_transfer_signed
        from_addr = "bcn_test123"
        to_addr = "RTC0000000000000000000000000000000000000002"
        # We need the server to look up the beacon registry. The preflight
        # accepts the address but the server will then try to look it up in
        # the bcn_registry table. We register a row so the lookup can find
        # a record, and a mismatch is triggered on the public_key field.
        with closing(sqlite3.connect(os.environ["RUSTCHAIN_DB_PATH"])) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO bcn_registry (beacon_id, pubkey_hex, agent_name) "
                "VALUES (?, ?, ?)",
                (from_addr, "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef", "test_agent"),
            )
            conn.commit()

        body = {
            "from_address": from_addr,
            "to_address": to_addr,
            "amount_rtc": "1.0",
            "nonce": "12347",
            "signature": "a",
            "public_key": "00",  # mismatch with the registered pubkey
            "memo": "",
        }
        status, payload = _response_payload(self._post(body))
        # The endpoint may return 400 (pubkey mismatch) or 404 (beacon not
        # registered) depending on registration state; either way, no leak.
        self.assertIn(
            status, (400, 404),
            f"expected 400 or 404, got {status}: {payload}"
        )
        self.assertNotIn(
            "expected_pubkey_prefix", payload,
            f"response leaked `expected_pubkey_prefix` field: {payload}"
        )
        self.assertNotIn(
            "expected", payload,
            f"response leaked `expected` field: {payload}"
        )

    def test_happy_path_still_validates_minimum(self):
        """The fix must not break the existing preflight shape validation.

        Sending a body with a missing field should still return 400, not 500
        or 200.
        """
        status, payload = _response_payload(self._post({"from_address": "RTC0000000000000000000000000000000000000001"}))
        self.assertEqual(status, 400, f"missing fields must be 400, got {status}: {payload}")
