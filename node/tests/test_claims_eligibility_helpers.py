# SPDX-License-Identifier: MIT

import sqlite3

from claims_eligibility import (
    check_pending_claim,
    get_wallet_address,
    is_epoch_settled,
    validate_miner_id_format,
)


def test_validate_miner_id_format_accepts_safe_ids():
    assert validate_miner_id_format("miner-01_ALPHA") is True


def test_validate_miner_id_format_rejects_empty_long_and_special_chars():
    assert validate_miner_id_format("") is False
    assert validate_miner_id_format("a" * 129) is False
    assert validate_miner_id_format("miner/01") is False
    assert validate_miner_id_format(None) is False


def test_get_wallet_address_prefers_latest_registered_wallet(tmp_path):
    db = tmp_path / "node.db"
    with sqlite3.connect(db) as conn:
        conn.execute(
            "CREATE TABLE miner_wallets (miner_id TEXT, wallet_address TEXT, created_at INTEGER)"
        )
        conn.executemany(
            "INSERT INTO miner_wallets VALUES (?, ?, ?)",
            [("miner1", "RTC-old", 1), ("miner1", "RTC-new", 2)],
        )

    assert get_wallet_address(str(db), "miner1") == "RTC-new"


def test_get_wallet_address_falls_back_to_attestation_wallet(tmp_path):
    db = tmp_path / "node.db"
    with sqlite3.connect(db) as conn:
        conn.execute(
            "CREATE TABLE miner_attest_recent (miner TEXT, wallet_address TEXT, ts_ok INTEGER)"
        )
        conn.executemany(
            "INSERT INTO miner_attest_recent VALUES (?, ?, ?)",
            [("miner1", "RTC-old", 1), ("miner1", "RTC-new", 2)],
        )

    assert get_wallet_address(str(db), "miner1") == "RTC-new"


def test_check_pending_claim_only_counts_active_statuses(tmp_path):
    db = tmp_path / "node.db"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE claims (claim_id TEXT, miner_id TEXT, epoch INTEGER, status TEXT)")
        conn.executemany(
            "INSERT INTO claims VALUES (?, ?, ?, ?)",
            [("done", "miner1", 7, "paid"), ("active", "miner1", 8, "verifying")],
        )

    assert check_pending_claim(str(db), "miner1", 7) is False
    assert check_pending_claim(str(db), "miner1", 8) is True


def test_is_epoch_settled_uses_database_state_when_present(tmp_path):
    db = tmp_path / "node.db"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE epoch_state (epoch INTEGER, settled INTEGER)")
        conn.executemany("INSERT INTO epoch_state VALUES (?, ?)", [(3, 0), (4, 1)])

    assert is_epoch_settled(str(db), 3, current_slot=10_000) is False
    assert is_epoch_settled(str(db), 4, current_slot=10_000) is True
