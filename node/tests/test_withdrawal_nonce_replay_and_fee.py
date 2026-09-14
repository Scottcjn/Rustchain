# SPDX-License-Identifier: MIT
"""Regression tests for the withdrawal off-ramp audit (2026-09-10):

  #1  nonce type-encoding replay — a signature is verified over the STRINGIFIED
      nonce (f"...:{nonce}") while the dedup key is stored TEXT. JSON bool `true`
      and the string "True" render identically in the signed message but stored as
      distinct dedup keys, so one signature could be replayed. Fix: reject bool
      nonces and canonicalize the nonce to its signed string form, so int 5 and
      str "5" collapse to the same dedup key.

  #5  fee semantics — the wallet is debited amount + fee (fee on top) and the
      destination receives `amount`; the response must report that, not the old
      contradictory net_amount = amount - fee.
"""
import base64
import importlib.util
import os
import sqlite3
import sys
import tempfile
import time
import unittest

NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULE_PATH = os.path.join(NODE_DIR, "rustchain_v2_integrated_v2.2.1_rip200.py")


class TestWithdrawalNonceReplayAndFee(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls._prev_db = os.environ.get("RUSTCHAIN_DB_PATH")
        cls._prev_admin = os.environ.get("RC_ADMIN_KEY")
        os.environ["RUSTCHAIN_DB_PATH"] = os.path.join(cls._tmp.name, "import.db")
        os.environ["RC_ADMIN_KEY"] = "0123456789abcdef0123456789abcdef"
        if NODE_DIR not in sys.path:
            sys.path.insert(0, NODE_DIR)
        spec = importlib.util.spec_from_file_location("rc_nonce_fee_test", MODULE_PATH)
        cls.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.mod)

    @classmethod
    def tearDownClass(cls):
        for k, v in (("RUSTCHAIN_DB_PATH", cls._prev_db), ("RC_ADMIN_KEY", cls._prev_admin)):
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        try:
            cls._tmp.cleanup()
        except OSError:
            pass

    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.mod.DB_PATH = self.db_path
        self._orig_verify = self.mod.verify_sr25519_signature
        self.mod.verify_sr25519_signature = lambda *_a, **_k: True
        self._create_schema()

    def tearDown(self):
        self.mod.verify_sr25519_signature = self._orig_verify
        try:
            os.unlink(self.db_path)
        except (FileNotFoundError, PermissionError):
            pass

    def _create_schema(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("CREATE TABLE balances (miner_pk TEXT PRIMARY KEY, balance_rtc REAL NOT NULL DEFAULT 0)")
            conn.execute("CREATE TABLE withdrawal_nonces (miner_pk TEXT NOT NULL, nonce TEXT NOT NULL, used_at INTEGER NOT NULL, PRIMARY KEY (miner_pk, nonce))")
            conn.execute("CREATE TABLE withdrawal_limits (miner_pk TEXT NOT NULL, date TEXT NOT NULL, total_withdrawn REAL DEFAULT 0, PRIMARY KEY (miner_pk, date))")
            conn.execute("CREATE TABLE miner_keys (miner_pk TEXT PRIMARY KEY, pubkey_sr25519 TEXT NOT NULL, registered_at INTEGER NOT NULL)")
            conn.execute("""CREATE TABLE withdrawals (withdrawal_id TEXT PRIMARY KEY, miner_pk TEXT NOT NULL,
                amount REAL NOT NULL, fee REAL NOT NULL, destination TEXT NOT NULL, signature TEXT NOT NULL,
                status TEXT DEFAULT 'pending', created_at INTEGER NOT NULL)""")
            conn.execute("""CREATE TABLE fee_events (id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT NOT NULL,
                source_id TEXT, miner_pk TEXT, fee_rtc REAL NOT NULL, fee_urtc INTEGER NOT NULL,
                destination TEXT NOT NULL, created_at INTEGER NOT NULL)""")
            conn.execute("INSERT INTO balances VALUES ('miner-test', 100.0)")
            conn.execute("INSERT INTO balances VALUES ('founder_community', 0)")
            conn.execute("INSERT INTO miner_keys VALUES ('miner-test', ?, ?)", ("00" * 32, int(time.time())))

    def _payload(self, nonce, amount=1.0):
        return {
            "miner_pk": "miner-test",
            "amount": amount,
            "destination": "rtc-destination",
            "signature": base64.b64encode(b"\x00" * 64).decode("ascii"),
            "nonce": nonce,
        }

    def _withdrawals(self):
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute("SELECT COUNT(*) FROM withdrawals").fetchone()[0]

    # ---- #1 -------------------------------------------------------------
    def test_bool_nonce_rejected(self):
        """A JSON boolean nonce is the replay vector — must be rejected outright."""
        with self.mod.app.test_client() as client:
            resp = client.post("/withdraw/request", json=self._payload(True))
        self.assertEqual(resp.status_code, 400)
        self.assertIn("nonce", resp.get_json().get("error", "").lower())
        self.assertEqual(self._withdrawals(), 0)

    def test_int_and_str_nonce_share_dedup_key(self):
        """int 5 and str "5" render to the same signed form; the second must be a
        replay, not a second payout (canonicalization closes the divergence)."""
        with self.mod.app.test_client() as client:
            first = client.post("/withdraw/request", json=self._payload("5"))
            self.assertEqual(first.status_code, 200)
            second = client.post("/withdraw/request", json=self._payload(5))  # int, same signed form
        self.assertEqual(second.status_code, 400)
        self.assertIn("replay", second.get_json().get("error", "").lower())
        self.assertEqual(self._withdrawals(), 1)  # exactly one payout queued

    # ---- #5 -------------------------------------------------------------
    def test_fee_semantics_response_matches_debit(self):
        """Fee is charged on top: debit = amount + fee, destination receives amount.
        Response must report net_amount = amount (not the old amount - fee)."""
        with self.mod.app.test_client() as client:
            resp = client.post("/withdraw/request", json=self._payload("n-fee", amount=10.0))
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        fee = self.mod.WITHDRAWAL_FEE
        self.assertAlmostEqual(body["net_amount"], 10.0, places=6)
        self.assertAlmostEqual(body["total_debited"], 10.0 + fee, places=6)
        with sqlite3.connect(self.db_path) as conn:
            bal = conn.execute("SELECT balance_rtc FROM balances WHERE miner_pk='miner-test'").fetchone()[0]
        self.assertAlmostEqual(bal, 100.0 - (10.0 + fee), places=6)  # debited amount + fee


if __name__ == "__main__":
    unittest.main()
