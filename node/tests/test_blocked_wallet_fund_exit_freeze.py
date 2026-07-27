# SPDX-License-Identifier: MIT
"""
Regression: a wallet marked in the block/review registry must not be able to
move funds out.

The gate `wallet_review_gate_response()` (backed by `wallet_review_holds` and
the legacy `blocked_wallets` table) was wired to exactly one endpoint —
/attest/submit (line ~4631). Every fund-EXIT path (/withdraw/request,
/wallet/transfer/signed, /utxo/transfer) ignored it, so a wallet an operator
had just frozen for fraud/compromise could still drain its entire balance
before a maintainer released it. Freezing the ability to *earn* while leaving
the ability to *spend* wide open defeats the whole purpose of a review hold.

These tests drive the real Flask endpoints with a genuinely blocked wallet and
assert the request is refused (403 wallet_blocked) with the balance untouched.
They FAIL on the pre-fix code (which returns 404/401 from the later
registration/signature checks, having debited nothing only by accident) and
PASS once the gate is consulted on the sender before any state mutation.
"""

import gc
import importlib.util
import os
import shutil
import sqlite3
import sys
import tempfile
import time
import unittest


NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULE_PATH = os.path.join(NODE_DIR, "rustchain_v2_integrated_v2.2.1_rip200.py")

# Valid RTC address form (RTC + 40 hex) so it clears the transfer validator and
# reaches the sender block-gate rather than being rejected on address format.
BLOCKED = "RTC" + "a" * 40


class TestBlockedWalletFundExitFreeze(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.mkdtemp(prefix="blocked-fund-exit-")
        cls._prev_db_path = os.environ.get("RUSTCHAIN_DB_PATH")
        cls._prev_admin_key = os.environ.get("RC_ADMIN_KEY")
        os.environ["RUSTCHAIN_DB_PATH"] = os.path.join(cls._tmp, "import.db")
        os.environ["RC_ADMIN_KEY"] = "0123456789abcdef0123456789abcdef"

        if NODE_DIR not in sys.path:
            sys.path.insert(0, NODE_DIR)

        spec = importlib.util.spec_from_file_location(
            "rustchain_integrated_blocked_fund_exit_test", MODULE_PATH
        )
        cls.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.mod)
        cls.client = cls.mod.app.test_client()

        # Seed a blocked-registry entry and a balance for BLOCKED.
        with sqlite3.connect(cls.mod.DB_PATH) as conn:
            cls.mod.ensure_wallet_review_tables(conn)
            conn.execute(
                """INSERT INTO wallet_review_holds
                   (wallet, status, reason, coach_note, reviewer_note, created_at, reviewed_at)
                   VALUES (?, 'blocked', 'fraud-review', '', '', ?, 0)""",
                (BLOCKED, int(time.time())),
            )
            conn.execute(
                """CREATE TABLE IF NOT EXISTS balances (
                       miner_id TEXT PRIMARY KEY, miner_pk TEXT,
                       amount_i64 INTEGER DEFAULT 0, balance_rtc REAL DEFAULT 0)"""
            )
            conn.execute(
                "INSERT OR REPLACE INTO balances (miner_id, miner_pk, amount_i64, balance_rtc) "
                "VALUES (?, ?, ?, ?)",
                (BLOCKED, BLOCKED, 100 * cls.mod.ACCOUNT_UNIT, 100.0),
            )
            conn.commit()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.mod.app.do_teardown_appcontext()
        except Exception:
            pass
        cls.client = None
        cls.mod = None
        for key, prev in (
            ("RUSTCHAIN_DB_PATH", cls._prev_db_path),
            ("RC_ADMIN_KEY", cls._prev_admin_key),
        ):
            if prev is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = prev
        gc.collect()
        shutil.rmtree(cls._tmp, ignore_errors=True)

    def _balance_i64(self):
        with sqlite3.connect(self.mod.DB_PATH) as conn:
            row = conn.execute(
                "SELECT amount_i64 FROM balances WHERE miner_id = ?", (BLOCKED,)
            ).fetchone()
        return row[0] if row else 0

    def test_withdraw_from_blocked_wallet_denied(self):
        before = self._balance_i64()
        resp = self.client.post(
            "/withdraw/request",
            json={
                "miner_pk": BLOCKED,
                "amount": 10,
                "destination": "RTCsomewhereelse00000000000000000000000000",
                "signature": "00",
                "nonce": "n-block-1",
            },
        )
        self.assertEqual(resp.status_code, 403, resp.get_json())
        self.assertEqual(resp.get_json().get("error"), "wallet_blocked")
        self.assertEqual(self._balance_i64(), before, "balance must be untouched")

    def test_signed_transfer_from_blocked_wallet_denied(self):
        before = self._balance_i64()
        resp = self.client.post(
            "/wallet/transfer/signed",
            json={
                "from_address": BLOCKED,
                "to_address": "RTC" + "b" * 40,
                "amount_rtc": 10,
                "nonce": int(time.time()),
                "signature": "00",
                "public_key": "00" * 32,
            },
        )
        # 400 only if the payload is rejected before the gate; the gate must win.
        self.assertEqual(resp.status_code, 403, resp.get_json())
        self.assertEqual(resp.get_json().get("error"), "wallet_blocked")
        self.assertEqual(self._balance_i64(), before, "balance must be untouched")


if __name__ == "__main__":
    unittest.main()
