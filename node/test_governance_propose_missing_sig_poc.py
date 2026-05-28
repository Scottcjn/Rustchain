# SPDX-License-Identifier: MIT
"""
PoC: POST /governance/propose accepts any wallet address as the proposer
without Ed25519 signature verification.

The sister endpoint /governance/vote requires a valid signature, nonce,
and public_key that derives to the voter wallet. /governance/propose has
no such check: any caller who knows a wallet address with > 10 RTC can
submit governance proposals attributed to that wallet.

Attack scenario:
  1. Attacker queries GET /balance/<victim_pk> and finds a wallet with
     sufficient RTC balance.
  2. Attacker sends POST /governance/propose with
       {"wallet": "<victim>", "title": "...", "description": "..."}
  3. The proposal is created, permanently attributed to the victim wallet,
     with no signature verification and no way for the victim to prevent it.

Fix: add Ed25519 signature verification (nonce, signature, public_key)
identical to the pattern already used in /governance/vote.
"""

import json
import sqlite3
import tempfile
import os
import unittest


_BALANCE_UNIT = 1_000_000   # 1 RTC = 1_000_000 i64 units
_MIN_BALANCE  = 10          # GOVERNANCE_MIN_PROPOSER_BALANCE_RTC


def _make_db(path: str, wallet: str, balance_rtc: float) -> None:
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS balances "
        "(miner_pk TEXT PRIMARY KEY, balance_rtc REAL NOT NULL DEFAULT 0)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS governance_proposals ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "proposer_wallet TEXT NOT NULL, "
        "title TEXT NOT NULL, "
        "description TEXT NOT NULL, "
        "created_at INTEGER NOT NULL, "
        "activated_at INTEGER, "
        "ends_at INTEGER, "
        "status TEXT NOT NULL DEFAULT 'draft', "
        "yes_weight REAL NOT NULL DEFAULT 0, "
        "no_weight REAL NOT NULL DEFAULT 0)"
    )
    conn.execute(
        "INSERT INTO balances (miner_pk, balance_rtc) VALUES (?, ?)",
        (wallet, balance_rtc),
    )
    conn.commit()
    conn.close()


def _balance_i64_for_wallet(conn: sqlite3.Connection, wallet: str) -> int:
    row = conn.execute(
        "SELECT balance_rtc FROM balances WHERE miner_pk = ?", (wallet,)
    ).fetchone()
    return int((row[0] if row else 0.0) * _BALANCE_UNIT)


def _propose_unauthenticated(
    conn: sqlite3.Connection,
    wallet: str,
    title: str,
    description: str,
    min_balance: float = _MIN_BALANCE,
) -> dict:
    """
    Simulates the VULNERABLE governance_propose() logic: no signature check.
    Returns the inserted proposal dict or an error dict.
    """
    import time as _time
    balance_i64  = _balance_i64_for_wallet(conn, wallet)
    balance_rtc  = balance_i64 / _BALANCE_UNIT
    if balance_rtc <= min_balance:
        return {"ok": False, "error": "insufficient_balance"}

    now      = int(_time.time())
    ends_at  = now + 7 * 24 * 3600
    c = conn.cursor()
    c.execute(
        "INSERT INTO governance_proposals "
        "(proposer_wallet, title, description, created_at, activated_at, ends_at, status)"
        " VALUES (?, ?, ?, ?, ?, ?, 'active')",
        (wallet, title, description, now, now, ends_at),
    )
    conn.commit()
    return {"ok": True, "proposal_id": c.lastrowid, "proposer": wallet}


def _propose_authenticated(
    conn: sqlite3.Connection,
    wallet: str,
    title: str,
    description: str,
    nonce: str,
    public_key: str,
    signature: str,
    min_balance: float = _MIN_BALANCE,
) -> dict:
    """
    Simulates the FIXED governance_propose() logic: requires valid signature.
    Returns an error dict if signature fields are absent.
    """
    if not all([nonce, public_key, signature]):
        return {"ok": False, "error": "nonce, signature, public_key are required"}
    # In the real implementation address_from_pubkey() and verify_rtc_signature()
    # are called here. This stub just checks that the fields are present.
    return {"ok": True, "authenticated": True}


class TestGovernanceProposeSignature(unittest.TestCase):

    def setUp(self):
        self._victim_wallet = "RTC" + "a" * 40
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        _make_db(self._tmp.name, self._victim_wallet, 100.0)   # victim has 100 RTC

    def tearDown(self):
        os.unlink(self._tmp.name)

    def test_unauthenticated_proposal_succeeds_without_signature(self):
        """
        Documents the vulnerability: a proposal can be created for any wallet
        with sufficient balance without proving ownership of that wallet.
        """
        with sqlite3.connect(self._tmp.name) as conn:
            result = _propose_unauthenticated(
                conn,
                wallet=self._victim_wallet,   # attacker uses victim's address
                title="Attacker Spam Proposal",
                description="This proposal was submitted without signature verification.",
            )
        self.assertTrue(result["ok"],
                        "Unauthenticated proposal must succeed (demonstrates vulnerability)")
        self.assertEqual(result["proposer"], self._victim_wallet,
                         "Proposal is attributed to the victim wallet the attacker provided")

    def test_authenticated_proposal_requires_signature_fields(self):
        """
        Documents the expected fixed behaviour: missing signature fields
        cause the endpoint to return an error before any DB write.
        """
        with sqlite3.connect(self._tmp.name) as conn:
            result = _propose_authenticated(
                conn,
                wallet=self._victim_wallet,
                title="Legitimate Proposal",
                description="Backed by a real Ed25519 signature.",
                nonce="",          # missing
                public_key="",     # missing
                signature="",      # missing
            )
        self.assertFalse(result["ok"],
                         "Missing signature fields must be rejected")
        self.assertIn("nonce", result["error"],
                      "Error message must mention the missing field(s)")

    def test_impersonation_creates_spurious_proposal_in_db(self):
        """
        Confirms that the unauthenticated path leaves a persistent record
        attributed to the victim wallet with no way for the victim to prevent it.
        """
        spam_title = "SPAM: proposal 42"
        with sqlite3.connect(self._tmp.name) as conn:
            _propose_unauthenticated(
                conn,
                wallet=self._victim_wallet,
                title=spam_title,
                description="x" * 1000,
            )
            rows = conn.execute(
                "SELECT title, proposer_wallet FROM governance_proposals"
            ).fetchall()

        self.assertEqual(len(rows), 1, "Exactly one proposal should be in the DB")
        self.assertEqual(rows[0][0], spam_title)
        self.assertEqual(rows[0][1], self._victim_wallet,
                         "Proposal is permanently attributed to the victim wallet")

    def test_insufficient_balance_is_still_rejected(self):
        """
        The balance check is orthogonal to signature verification and must
        remain in place after the fix is applied.
        """
        poor_wallet = "RTC" + "b" * 40
        with sqlite3.connect(self._tmp.name) as conn:
            _make_db(self._tmp.name, poor_wallet, 5.0)   # only 5 RTC, below 10 minimum
            result = _propose_unauthenticated(conn, poor_wallet, "t", "d")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "insufficient_balance")


if __name__ == '__main__':
    unittest.main()
