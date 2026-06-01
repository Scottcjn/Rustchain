# SPDX-License-Identifier: MIT
"""
PoC: governance.py create_proposal balance check fails on schema-B nodes.

Schema A (legacy):  balances(miner_pk TEXT PRIMARY KEY, balance_rtc REAL)
Schema B (current): balances(miner_id TEXT PRIMARY KEY, amount_i64 INTEGER)

Before the fix, _create_proposal_ queried `balance_rtc FROM balances WHERE
miner_pk = ?` unconditionally. On a schema-B node this raises
sqlite3.OperationalError (no such column: balance_rtc), which is caught by
the outer `except Exception` and returns HTTP 500, blocking all governance
proposals regardless of the miner's actual balance.

After the fix, _balance_rtc_for_miner and _deduct_proposal_fee probe both
schemas, so proposal creation succeeds on either.
"""

import sqlite3
import unittest

from governance import _balance_rtc_for_miner, _deduct_proposal_fee


def _schema_a_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE balances (miner_pk TEXT PRIMARY KEY, balance_rtc REAL DEFAULT 0)"
    )
    conn.execute(
        "INSERT INTO balances (miner_pk, balance_rtc) VALUES (?, ?)",
        ("deadbeef01", 50.0),
    )
    conn.commit()
    return conn


def _schema_b_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE balances (miner_id TEXT PRIMARY KEY, amount_i64 INTEGER DEFAULT 0)"
    )
    conn.execute(
        "INSERT INTO balances (miner_id, amount_i64) VALUES (?, ?)",
        ("deadbeef01", 50_000_000),  # 50 RTC
    )
    conn.commit()
    return conn


class TestBalanceRtcForMiner(unittest.TestCase):

    def test_schema_a_reads_balance(self):
        with _schema_a_db() as conn:
            bal = _balance_rtc_for_miner(conn, "deadbeef01")
        self.assertAlmostEqual(bal, 50.0)

    def test_schema_b_reads_balance(self):
        with _schema_b_db() as conn:
            bal = _balance_rtc_for_miner(conn, "deadbeef01")
        self.assertAlmostEqual(bal, 50.0)

    def test_schema_a_unknown_miner_returns_zero(self):
        with _schema_a_db() as conn:
            bal = _balance_rtc_for_miner(conn, "unknown")
        self.assertEqual(bal, 0.0)

    def test_schema_b_unknown_miner_returns_zero(self):
        with _schema_b_db() as conn:
            bal = _balance_rtc_for_miner(conn, "unknown")
        self.assertEqual(bal, 0.0)


class TestDeductProposalFee(unittest.TestCase):

    def test_schema_a_deducts_fee(self):
        conn = _schema_a_db()
        _deduct_proposal_fee(conn, "deadbeef01", 10.0)
        row = conn.execute(
            "SELECT balance_rtc FROM balances WHERE miner_pk = ?", ("deadbeef01",)
        ).fetchone()
        self.assertAlmostEqual(row[0], 40.0)
        conn.close()

    def test_schema_b_deducts_fee(self):
        conn = _schema_b_db()
        _deduct_proposal_fee(conn, "deadbeef01", 10.0)
        row = conn.execute(
            "SELECT amount_i64 FROM balances WHERE miner_id = ?", ("deadbeef01",)
        ).fetchone()
        self.assertEqual(row[0], 40_000_000)
        conn.close()

    def test_schema_a_insufficient_balance_not_deducted_when_caller_checks(self):
        conn = _schema_a_db()
        bal = _balance_rtc_for_miner(conn, "deadbeef01")
        self.assertGreater(bal, 10.0)
        _deduct_proposal_fee(conn, "deadbeef01", 10.0)
        remaining = _balance_rtc_for_miner(conn, "deadbeef01")
        self.assertAlmostEqual(remaining, 40.0)
        conn.close()

    def test_schema_b_insufficient_balance_not_deducted_when_caller_checks(self):
        conn = _schema_b_db()
        bal = _balance_rtc_for_miner(conn, "deadbeef01")
        self.assertGreater(bal, 10.0)
        _deduct_proposal_fee(conn, "deadbeef01", 10.0)
        remaining = _balance_rtc_for_miner(conn, "deadbeef01")
        self.assertAlmostEqual(remaining, 40.0)
        conn.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
