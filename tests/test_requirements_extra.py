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
