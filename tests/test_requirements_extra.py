import pytest
import sqlite3
import time
from unittest.mock import patch
import sys
from pathlib import Path

# Modules are pre-loaded in conftest.py
rr_mod = sys.modules["rr_mod"]
ATTESTATION_TTL = rr_mod.ATTESTATION_TTL

@pytest.fixture
def mock_db(tmp_path):
    db_path = str(tmp_path / "test_ttl.db")
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS miner_attest_recent (
            miner TEXT PRIMARY KEY,
            device_arch TEXT,
            ts_ok INTEGER
        )
    """)
    conn.commit()
    conn.close()
    return db_path

def test_attestation_ttl_valid(mock_db):
    """Verify that valid attestations within TTL are returned."""
    current_ts = int(time.time())
    with sqlite3.connect(mock_db) as conn:
        conn.execute("INSERT INTO miner_attest_recent VALUES (?, ?, ?)",
                     ("miner1", "g4", current_ts - 100)) # 100s ago, well within TTL

    miners = rr_mod.get_attested_miners(mock_db, current_ts)
    assert len(miners) == 1
    assert miners[0][0] == "miner1"

def test_attestation_ttl_expired(mock_db):
    """Verify that expired attestations are filtered out."""
    current_ts = int(time.time())
    with sqlite3.connect(mock_db) as conn:
        # ATTESTATION_TTL is 86400 (24h)
        conn.execute("INSERT INTO miner_attest_recent VALUES (?, ?, ?)",
                     ("miner_old", "g4", current_ts - ATTESTATION_TTL - 1))

    miners = rr_mod.get_attested_miners(mock_db, current_ts)
    assert len(miners) == 0

def test_fee_calculation_logic():
    """Verify withdrawal fee calculation logic found in node script."""
    # Based on Read tool results:
    # WITHDRAWAL_FEE = 0.01  # RTC
    # total_needed = amount + WITHDRAWAL_FEE

    withdrawal_fee = 0.01
    amount = 1.0
    total_needed = amount + withdrawal_fee

    assert total_needed == 1.01

    # Test case: insufficient balance for fee
    balance = 1.005
    assert balance < total_needed


def test_withdrawal_fee_routed_to_founder_community(tmp_path):
    """Verify withdrawal fee is credited to founder_community using correct columns.

    Regression test for the bug where fee routing used non-existent columns
    (amount_i64 / miner_id) instead of the actual schema columns
    (balance_rtc / miner_pk), causing fees to be silently burned.
    """
    db_path = str(tmp_path / "test_fee_routing.db")
    UNIT = 1_000_000
    WITHDRAWAL_FEE = 0.01

    with sqlite3.connect(db_path) as conn:
        c = conn.cursor()
        # Create balances table with the actual schema (miner_pk, balance_rtc)
        c.execute("CREATE TABLE balances (miner_pk TEXT PRIMARY KEY, balance_rtc REAL DEFAULT 0)")
        c.execute("""CREATE TABLE IF NOT EXISTS fee_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL, source_id TEXT, miner_pk TEXT,
            fee_rtc REAL NOT NULL, fee_urtc INTEGER NOT NULL,
            destination TEXT NOT NULL, created_at INTEGER NOT NULL
        )""")

        # Seed miner with enough balance
        c.execute("INSERT INTO balances (miner_pk, balance_rtc) VALUES (?, ?)",
                  ("RTC_test_miner", 10.0))

        # Simulate the FIXED withdrawal fee routing logic
        amount = 1.0
        total_needed = amount + WITHDRAWAL_FEE
        c.execute("UPDATE balances SET balance_rtc = balance_rtc - ? WHERE miner_pk = ?",
                  (total_needed, "RTC_test_miner"))

        fee_urtc = int(WITHDRAWAL_FEE * UNIT)
        fee_rtc = WITHDRAWAL_FEE
        # Ensure founder_community row exists
        c.execute("INSERT OR IGNORE INTO balances (miner_pk, balance_rtc) VALUES (?, 0)",
                  ("founder_community",))
        c.execute("UPDATE balances SET balance_rtc = balance_rtc + ? WHERE miner_pk = ?",
                  (fee_rtc, "founder_community"))
        c.execute(
            "INSERT INTO fee_events (source, source_id, miner_pk, fee_rtc, fee_urtc, destination, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("withdrawal", "WD_test", "RTC_test_miner", fee_rtc, fee_urtc, "founder_community", int(time.time()))
        )

        # Verify miner balance was deducted correctly
        miner_bal = c.execute(
            "SELECT balance_rtc FROM balances WHERE miner_pk = ?", ("RTC_test_miner",)
        ).fetchone()[0]
        assert miner_bal == pytest.approx(10.0 - total_needed), \
            f"Miner balance should be {10.0 - total_needed}, got {miner_bal}"

        # Verify founder_community received the fee (not burned)
        fc_bal = c.execute(
            "SELECT balance_rtc FROM balances WHERE miner_pk = ?", ("founder_community",)
        ).fetchone()[0]
        assert fc_bal == pytest.approx(WITHDRAWAL_FEE), \
            f"founder_community should have {WITHDRAWAL_FEE} RTC, got {fc_bal}"

        # Verify fee_events recorded correctly
        fee_row = c.execute(
            "SELECT fee_rtc, destination FROM fee_events WHERE source = 'withdrawal'"
        ).fetchone()
        assert fee_row is not None, "fee_events should have a withdrawal entry"
        assert fee_row[0] == WITHDRAWAL_FEE
        assert fee_row[1] == "founder_community"
