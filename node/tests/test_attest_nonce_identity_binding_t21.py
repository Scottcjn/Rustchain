"""T2.1 regression: challenge nonces may be BOUND to the requesting identity.

`/attest/challenge` used to issue a free-floating nonce bound to nobody — any
claimed miner could consume any live nonce, so a harvested/MITM'd challenge could be
replayed under a different identity (feeds the T1.1 impersonation surface). T2.1 lets
the requester bind the nonce to its miner_id; a submission claiming a different
identity is rejected WITHOUT consuming the nonce (so it can't DoS the rightful owner).
Unbound nonces stay consumable by anyone (backward compatible for legacy miners).
"""
import importlib.util
import os
import sqlite3
import tempfile
import time
import unittest

NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULE_PATH = os.path.join(NODE_DIR, "rustchain_v2_integrated_v2.2.1_rip200.py")


class NonceIdentityBindingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        os.environ.setdefault("RUSTCHAIN_DB_PATH", os.path.join(cls._tmp.name, "t21.db"))
        os.environ.setdefault("RC_ADMIN_KEY", "0123456789abcdef0123456789abcdef")
        os.environ.setdefault("RUSTCHAIN_DISABLE_P2P_AUTO_START", "1")
        spec = importlib.util.spec_from_file_location("rcnode_t21_test", MODULE_PATH)
        cls.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.mod)

    def _conn(self):
        c = sqlite3.connect(":memory:")
        self.mod.attest_ensure_tables(c)
        c.commit()
        return c

    def _issue(self, c, nonce, bound_miner=None, ttl=300):
        c.execute("INSERT INTO nonces (nonce, expires_at, bound_miner) VALUES (?, ?, ?)",
                  (nonce, int(time.time()) + ttl, bound_miner))
        c.commit()

    # --- schema ------------------------------------------------------------
    def test_ensure_tables_adds_bound_miner_column(self):
        c = self._conn()
        cols = [r[1] for r in c.execute("PRAGMA table_info(nonces)").fetchall()]
        self.assertIn("bound_miner", cols)

    def test_ensure_tables_migrates_legacy_nonces_table(self):
        """An existing 2-column nonces table must gain bound_miner in place (ALTER),
        not error and not drop rows."""
        c = sqlite3.connect(":memory:")
        c.execute("CREATE TABLE nonces (nonce TEXT PRIMARY KEY, expires_at INTEGER)")
        c.execute("INSERT INTO nonces (nonce, expires_at) VALUES ('legacy', ?)", (int(time.time()) + 300,))
        c.commit()
        self.mod.attest_ensure_tables(c)  # must ALTER, not raise
        cols = [r[1] for r in c.execute("PRAGMA table_info(nonces)").fetchall()]
        self.assertIn("bound_miner", cols)
        self.assertEqual(c.execute("SELECT bound_miner FROM nonces WHERE nonce='legacy'").fetchone()[0], None)

    # --- unbound (legacy) --------------------------------------------------
    def test_unbound_nonce_consumable_by_any_miner(self):
        c = self._conn()
        self._issue(c, "n-unbound", bound_miner=None)
        ok, err, _ = self.mod.attest_validate_and_store_nonce(c, miner="whoever-x", nonce="n-unbound")
        self.assertTrue(ok, err)

    # --- bound: matching identity -----------------------------------------
    def test_bound_nonce_consumed_by_matching_miner(self):
        c = self._conn()
        self._issue(c, "n-bound", bound_miner="g4-powerbook-115")
        ok, err, _ = self.mod.attest_validate_and_store_nonce(c, miner="g4-powerbook-115", nonce="n-bound")
        self.assertTrue(ok, err)
        # consumed: moved to used_nonces, removed from nonces
        self.assertEqual(c.execute("SELECT COUNT(*) FROM nonces WHERE nonce='n-bound'").fetchone()[0], 0)
        self.assertEqual(c.execute("SELECT COUNT(*) FROM used_nonces WHERE nonce='n-bound'").fetchone()[0], 1)

    # --- bound: mismatched identity ---------------------------------------
    def test_bound_nonce_rejected_for_other_miner_and_preserved(self):
        c = self._conn()
        self._issue(c, "n-victim", bound_miner="g4-powerbook-115")
        # attacker tries to consume the victim's bound challenge
        ok, err, _ = self.mod.attest_validate_and_store_nonce(c, miner="attacker-wallet", nonce="n-victim")
        self.assertFalse(ok)
        self.assertEqual(err, "nonce_identity_mismatch")
        # NOT consumed — still available for the rightful owner (no DoS)
        self.assertEqual(c.execute("SELECT COUNT(*) FROM nonces WHERE nonce='n-victim'").fetchone()[0], 1)
        self.assertEqual(c.execute("SELECT COUNT(*) FROM used_nonces WHERE nonce='n-victim'").fetchone()[0], 0)
        # rightful owner can still use it afterward
        ok2, err2, _ = self.mod.attest_validate_and_store_nonce(c, miner="g4-powerbook-115", nonce="n-victim")
        self.assertTrue(ok2, err2)

    def test_bound_nonce_rejected_when_no_identity_supplied(self):
        """Codex audit: a bound nonce must NOT be consumable by a caller that omits its
        identity (required_miner None/empty) — otherwise binding is trivially dodged."""
        c = self._conn()
        self._issue(c, "n-noident", bound_miner="owner")
        for bad in (None, "", "   "):
            ok, err, _ = self.mod.attest_validate_challenge(c, "n-noident", required_miner=bad)
            self.assertFalse(ok)
            self.assertEqual(err, "nonce_identity_mismatch")
            self.assertEqual(c.execute("SELECT COUNT(*) FROM nonces WHERE nonce='n-noident'").fetchone()[0], 1)

    def test_ensure_tables_idempotent_double_call(self):
        """The race-safe ALTER must be idempotent: a second ensure_tables call must not
        raise duplicate-column, and must not add the column twice."""
        c = self._conn()                       # ensured once
        self.mod.attest_ensure_tables(c)       # second call — must not raise
        self.mod.attest_ensure_tables(c)       # third for good measure
        cols = [r[1] for r in c.execute("PRAGMA table_info(nonces)").fetchall()]
        self.assertEqual(cols.count("bound_miner"), 1)

    def test_validate_challenge_mismatch_does_not_delete(self):
        """Lower-level guard: attest_validate_challenge must not consume on mismatch."""
        c = self._conn()
        self._issue(c, "n-low", bound_miner="owner")
        ok, err, _ = self.mod.attest_validate_challenge(c, "n-low", required_miner="intruder")
        self.assertFalse(ok)
        self.assertEqual(err, "nonce_identity_mismatch")
        self.assertEqual(c.execute("SELECT COUNT(*) FROM nonces WHERE nonce='n-low'").fetchone()[0], 1)

    # --- replay (unchanged behavior) --------------------------------------
    def test_replay_rejected_after_consume(self):
        c = self._conn()
        self._issue(c, "n-replay", bound_miner="g5-selena-179")
        ok, _, _ = self.mod.attest_validate_and_store_nonce(c, miner="g5-selena-179", nonce="n-replay")
        self.assertTrue(ok)
        ok2, err2, _ = self.mod.attest_validate_and_store_nonce(c, miner="g5-selena-179", nonce="n-replay")
        self.assertFalse(ok2)
        self.assertEqual(err2, "nonce_replay")


if __name__ == "__main__":
    unittest.main()
