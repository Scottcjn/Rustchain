# SPDX-License-Identifier: MIT

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import claims_eligibility
from claims_eligibility import (
    BLOCK_TIME,
    GENESIS_TIMESTAMP,
    check_epoch_participation,
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


def test_check_epoch_participation_prefers_epoch_enroll_snapshot(tmp_path):
    db = tmp_path / "node.db"
    epoch = 7
    miner = "miner-delayed-claim"
    later_ts = GENESIS_TIMESTAMP + ((epoch + 3) * 144 * BLOCK_TIME)
    with sqlite3.connect(db) as conn:
        conn.execute(
            "CREATE TABLE epoch_enroll (epoch INTEGER, miner_pk TEXT, weight REAL DEFAULT 1.0)"
        )
        conn.execute(
            """
            CREATE TABLE miner_attest_recent (
                miner TEXT,
                device_arch TEXT,
                ts_ok INTEGER,
                fingerprint_passed INTEGER DEFAULT 1,
                entropy_score REAL
            )
            """
        )
        conn.execute("INSERT INTO epoch_enroll VALUES (?, ?, ?)", (epoch, miner, 1.0))
        # miner_attest_recent only contains a later attestation.  The miner was
        # still enrolled in the claimed epoch, so participation must not depend
        # on the rolling recent-attestation table retaining an in-window row.
        conn.execute(
            "INSERT INTO miner_attest_recent VALUES (?, ?, ?, ?, ?)",
            (miner, "modern", later_ts, 1, 0.5),
        )

    participated, epoch_data = check_epoch_participation(str(db), miner, epoch)

    assert participated is True
    assert epoch_data["epoch"] == epoch
    assert epoch_data["source"] == "epoch_enroll"
    assert epoch_data["device_arch"] == "modern"


def test_is_epoch_settled_uses_database_state_when_present(tmp_path):
    db = tmp_path / "node.db"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE epoch_state (epoch INTEGER, settled INTEGER)")
        conn.executemany("INSERT INTO epoch_state VALUES (?, ?)", [(3, 0), (4, 1)])

    assert is_epoch_settled(str(db), 3, current_slot=10_000) is False
    assert is_epoch_settled(str(db), 4, current_slot=10_000) is True


def test_check_claim_eligibility_reports_rtc_with_urtc_unit(monkeypatch):
    monkeypatch.setattr(claims_eligibility, "is_epoch_settled", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        claims_eligibility,
        "get_miner_attestation",
        lambda *args, **kwargs: {
            "last_seen_ts": GENESIS_TIMESTAMP,
            "device_arch": "modern",
        },
    )
    monkeypatch.setattr(claims_eligibility, "get_chain_age_years", lambda current_slot: 0)
    monkeypatch.setattr(claims_eligibility, "get_time_aged_multiplier", lambda *args: 1.0)
    monkeypatch.setattr(
        claims_eligibility,
        "check_epoch_participation",
        lambda *args, **kwargs: (True, {"fingerprint_passed": 1, "entropy_score": 0.5}),
    )
    monkeypatch.setattr(claims_eligibility, "get_wallet_address", lambda *args: "RTC" + "A" * 20)
    monkeypatch.setattr(claims_eligibility, "check_pending_claim", lambda *args: False)
    monkeypatch.setattr(claims_eligibility, "HAVE_FLEET_IMMUNE", False)
    monkeypatch.setattr(claims_eligibility, "calculate_epoch_reward", lambda *args: 1_500_000)

    result = claims_eligibility.check_claim_eligibility(
        db_path="unused.db",
        miner_id="miner1",
        epoch=1,
        current_slot=10_000,
        current_ts=GENESIS_TIMESTAMP,
    )

    assert result["eligible"] is True
    assert result["reward_urtc"] == 1_500_000
    assert result["reward_rtc"] == 1.5
