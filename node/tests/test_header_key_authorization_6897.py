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

    # --- _register_header_key: grandfather + multi-device (iteration 2) -----
    def test_register_header_key_does_not_autoseed_bootstrap(self):
        """_register_header_key must NOT auto-allowlist. Persisting trust-on-first-use
        keys into strict mode is the takeover this guard prevents; the allowlist is
        admin-only (+ one-time migration backfill). It writes keys, not bootstrap."""
        self._strict(False)
        ident = "g5-powerbook-130"
        self.assertTrue(self.mod._register_header_key(self.conn, ident, VICTIM_PK))
        self.assertIsNotNone(self.conn.execute(
            "SELECT 1 FROM miner_header_keys WHERE miner_id=? AND pubkey_hex=?", (ident, VICTIM_PK)).fetchone())
        self.assertIsNone(self.conn.execute(  # NOT auto-allowlisted
            "SELECT 1 FROM miner_header_bootstrap WHERE miner_id=? AND pubkey_hex=?", (ident, VICTIM_PK)).fetchone())
        # under strict, after the key prunes, re-bootstrap requires an ADMIN seed
        self.conn.execute("DELETE FROM miner_header_keys WHERE miner_id=?", (ident,))
        self._strict(True)
        self.assertFalse(self._auth(ident, VICTIM_PK))     # not seeded -> denied (correct: TOFU untrusted)
        self._allow(ident, VICTIM_PK)                      # admin seeds the real producer
        self.assertTrue(self._auth(ident, VICTIM_PK))      # now allowed

    def test_allowlisted_multidevice_add_to_named_identity(self):
        """Admin-allowlisted additional key can be added to a named identity that
        already has a key (multi-device/rotation); a non-allowlisted key cannot."""
        ident = "power8-s824-sophia"
        self.conn.execute(
            "INSERT INTO miner_header_keys (miner_id, pubkey_hex) VALUES (?, ?)", (ident, VICTIM_PK))
        self._allow(ident, THIRD_PK)                       # admin pre-approves a 2nd device key
        self.assertTrue(self._auth(ident, THIRD_PK))       # allowlisted add allowed
        self.assertTrue(self._auth(ident, VICTIM_PK))      # idempotent re-register
        self.assertFalse(self._auth(ident, ATTACKER_PK))   # not allowlisted -> rejected

    def test_register_header_key_rejects_unauthorized_under_strict(self):
        self._strict(True)
        ident = "newcomer-named"
        self.assertFalse(self.mod._register_header_key(self.conn, ident, ATTACKER_PK))
        self.assertIsNone(self.conn.execute(
            "SELECT 1 FROM miner_header_keys WHERE miner_id=?", (ident,)).fetchone())

    def test_revoke_removes_from_allowlist(self):
        """Admin revoke (delete from both tables) retires a key so it can no longer
        re-bootstrap — pruning alone cannot retire an allowlisted key."""
        ident = "power8-s824-sophia"
        self._allow(ident, VICTIM_PK)
        self._strict(True)
        self.assertTrue(self._auth(ident, VICTIM_PK))      # allowlisted -> bootstrap ok
        # what the admin /miner/headerkey action=revoke does:
        self.conn.execute("DELETE FROM miner_header_keys WHERE miner_id=? AND pubkey_hex=?", (ident, VICTIM_PK))
        self.conn.execute("DELETE FROM miner_header_bootstrap WHERE miner_id=? AND pubkey_hex=?", (ident, VICTIM_PK))
        self.assertFalse(self._auth(ident, VICTIM_PK))     # revoked -> denied

    def test_backfill_is_one_time_not_every_startup(self):
        """Round-3 fix: the bootstrap backfill must NOT re-absorb keys on restart,
        or rollout-window TOFU keys would be silently allowlisted into strict mode."""
        dbp = self.mod.DB_PATH
        self.mod.init_db()       # first startup: applies schema v18 + one-time backfill
        c = sqlite3.connect(dbp)
        try:
            # a TOFU key registered during the strict-off rollout window (after upgrade)
            c.execute("INSERT OR IGNORE INTO miner_header_keys (miner_id, pubkey_hex) VALUES (?,?)",
                      ("tofu-rollout-id", VICTIM_PK))
            c.commit()
            self.mod.init_db()   # a SUBSEQUENT startup must not re-absorb it
            row = c.execute("SELECT 1 FROM miner_header_bootstrap WHERE miner_id=? AND pubkey_hex=?",
                            ("tofu-rollout-id", VICTIM_PK)).fetchone()
            self.assertIsNone(row, "one-time backfill must not re-absorb rollout-window TOFU keys")
        finally:
            c.close()

    # --- misc --------------------------------------------------------------
    def test_empty_pubkey_rejected(self):
        self.assertFalse(self._auth(_addr(VICTIM_PK), ""))
        self.assertFalse(self._auth("named", None))


if __name__ == "__main__":
    unittest.main()
