"""Regression test for the header-key takeover guard (_header_key_authorized).

Context: `miner_header_keys` is the trust anchor for block-header verification (a
header is accepted if signed by ANY registered key for the identity). The enroll
path's inputs are caller-controlled and the attestation signature only proves
possession of the *provided* pubkey, not ownership of the named identity. Without
a guard, a third party could attest as another wallet with their own key and ADD
their key to that wallet's valid-key set -> block-header forgery.

These tests assert `_header_key_authorized` allows only legitimate registrations.
"""
import hashlib
import importlib.util
import os
import sqlite3
import tempfile
import unittest

NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULE_PATH = os.path.join(NODE_DIR, "rustchain_v2_integrated_v2.2.1_rip200.py")

VICTIM_PK = "11" * 32     # 64 hex chars = 32 bytes
ATTACKER_PK = "22" * 32
THIRD_PK = "33" * 32


def _addr(pk):
    return "RTC" + hashlib.sha256(bytes.fromhex(pk)).hexdigest()[:40]


class HeaderKeyAuthorizationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        cls._prev_db = os.environ.get("RUSTCHAIN_DB_PATH")
        cls._prev_admin = os.environ.get("RC_ADMIN_KEY")
        os.environ["RUSTCHAIN_DB_PATH"] = os.path.join(cls._tmp.name, "hk.db")
        os.environ.setdefault("RC_ADMIN_KEY", "0123456789abcdef0123456789abcdef")
        spec = importlib.util.spec_from_file_location("rcnode_hk_auth_test", MODULE_PATH)
        cls.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.mod)
        # sanity: derivation matches the module's own
        assert cls.mod.address_from_pubkey(VICTIM_PK) == _addr(VICTIM_PK)

    @classmethod
    def tearDownClass(cls):
        if cls._prev_db is None:
            os.environ.pop("RUSTCHAIN_DB_PATH", None)
        else:
            os.environ["RUSTCHAIN_DB_PATH"] = cls._prev_db
        if cls._prev_admin is None:
            os.environ.pop("RC_ADMIN_KEY", None)
        else:
            os.environ["RC_ADMIN_KEY"] = cls._prev_admin
        cls._tmp.cleanup()

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.execute(
            "CREATE TABLE miner_header_keys (miner_id TEXT, pubkey_hex TEXT, "
            "PRIMARY KEY (miner_id, pubkey_hex))"
        )
        self.conn.execute(
            "CREATE TABLE miner_header_bootstrap (miner_id TEXT, pubkey_hex TEXT, "
            "PRIMARY KEY (miner_id, pubkey_hex))"
        )
        self._prev_strict = os.environ.get("RC_HEADER_KEY_STRICT_BOOTSTRAP")
        os.environ.pop("RC_HEADER_KEY_STRICT_BOOTSTRAP", None)  # default = off

    def tearDown(self):
        self.conn.close()
        if self._prev_strict is None:
            os.environ.pop("RC_HEADER_KEY_STRICT_BOOTSTRAP", None)
        else:
            os.environ["RC_HEADER_KEY_STRICT_BOOTSTRAP"] = self._prev_strict

    def _strict(self, on):
        if on:
            os.environ["RC_HEADER_KEY_STRICT_BOOTSTRAP"] = "1"
        else:
            os.environ.pop("RC_HEADER_KEY_STRICT_BOOTSTRAP", None)

    def _allow(self, identity, pubkey):
        self.conn.execute(
            "INSERT OR IGNORE INTO miner_header_bootstrap (miner_id, pubkey_hex) VALUES (?, ?)",
            (identity, pubkey),
        )

    def _auth(self, identity, pubkey):
        return self.mod._header_key_authorized(self.conn, identity, pubkey)

    def _register(self, identity, pubkey):
        self.conn.execute(
            "INSERT OR REPLACE INTO miner_header_keys (miner_id, pubkey_hex) VALUES (?, ?)",
            (identity, pubkey),
        )

    # --- self-authenticating identities -----------------------------------
    def test_rtc_address_holder_allowed(self):
        ident = _addr(VICTIM_PK)
        self.assertTrue(self._auth(ident, VICTIM_PK))

    def test_raw_pubkey_identity_allowed(self):
        self.assertTrue(self._auth(VICTIM_PK, VICTIM_PK))

    def test_attacker_cannot_take_over_rtc_address(self):
        ident = _addr(VICTIM_PK)
        self._register(ident, VICTIM_PK)          # victim establishes its key
        # Attacker attests as victim's wallet with their own key:
        self.assertFalse(self._auth(ident, ATTACKER_PK))

    # --- named / legacy identities -----------------------------------------
    def test_named_identity_bootstrap_then_locked(self):
        ident = "power8-s824-sophia"
        # First (legit) key bootstraps:
        self.assertTrue(self._auth(ident, VICTIM_PK))
        self._register(ident, VICTIM_PK)
        # Idempotent re-register of the same key is fine:
        self.assertTrue(self._auth(ident, VICTIM_PK))
        # Attacker can NOT add a new key to the established identity:
        self.assertFalse(self._auth(ident, ATTACKER_PK))
        self.assertFalse(self._auth(ident, THIRD_PK))

    # --- strict bootstrap (T1.1 TOFU fix) ----------------------------------
    def test_strict_off_named_bootstrap_still_allowed(self):
        """Default (flag off) preserves legacy first-write-wins for rollout."""
        self._strict(False)
        self.assertTrue(self._auth("power8-s824-sophia", VICTIM_PK))

    def test_strict_on_named_bootstrap_rejected_without_allowlist(self):
        """Strict mode closes the TOFU race: no allowlist entry -> reject."""
        self._strict(True)
        self.assertFalse(self._auth("power8-s824-sophia", ATTACKER_PK))

    def test_strict_on_named_bootstrap_allowed_when_allowlisted(self):
        self._strict(True)
        self._allow("power8-s824-sophia", VICTIM_PK)
        self.assertTrue(self._auth("power8-s824-sophia", VICTIM_PK))
        # attacker key still rejected even with a (different) allowlist entry present
        self.assertFalse(self._auth("power8-s824-sophia", ATTACKER_PK))

    def test_strict_on_pubkey_derived_self_bootstrap_still_allowed(self):
        """Self-authenticating identities never need the allowlist."""
        self._strict(True)
        self.assertTrue(self._auth(_addr(VICTIM_PK), VICTIM_PK))
        self.assertTrue(self._auth(VICTIM_PK, VICTIM_PK))

    # --- misc --------------------------------------------------------------
    def test_empty_pubkey_rejected(self):
        self.assertFalse(self._auth(_addr(VICTIM_PK), ""))
        self.assertFalse(self._auth("named", None))


if __name__ == "__main__":
    unittest.main()
