#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3
import sys
import threading


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "node"))

from claims_settlement import (
    generate_batch_id,
    process_claims_batch,
    settlement_batch_conditions_met,
)


def test_generate_batch_id_uses_database_sequence_under_concurrency(tmp_path):
    db_path = str(tmp_path / "claims.db")

    conn = sqlite3.connect(db_path)
    conn.close()

    with ThreadPoolExecutor(max_workers=8) as executor:
        batch_ids = list(executor.map(lambda _: generate_batch_id(db_path), range(20)))

    assert len(batch_ids) == 20
    assert len(set(batch_ids)) == 20

    day_prefix = "_".join(batch_ids[0].split("_")[:4])
    assert all(batch_id.startswith(f"{day_prefix}_") for batch_id in batch_ids)

    sequences = sorted(int(batch_id.rsplit("_", 1)[1]) for batch_id in batch_ids)
    assert sequences == list(range(1, 21))

    batch_day = day_prefix.removeprefix("batch_")
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT sequence FROM settlement_batch_sequence WHERE batch_day = ?",
            (batch_day,),
        ).fetchone()
    finally:
        conn.close()

    assert row == (20,)


def test_process_claims_batch_reserves_claims_before_broadcast(tmp_path, monkeypatch):
    db_path = str(tmp_path / "claims.db")
    now = 1_700_000_000
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE claims (
                claim_id TEXT PRIMARY KEY,
                miner_id TEXT,
                epoch INTEGER,
                wallet_address TEXT,
                reward_urtc INTEGER,
                status TEXT,
                submitted_at INTEGER,
                verified_at INTEGER,
                settled_at INTEGER,
                transaction_hash TEXT,
                settlement_batch TEXT,
                rejection_reason TEXT,
                signature TEXT,
                public_key TEXT,
                ip_address TEXT,
                user_agent TEXT,
                created_at INTEGER,
                updated_at INTEGER,
                UNIQUE(miner_id, epoch)
            )
        """)
        conn.execute("""
            INSERT INTO claims (
                claim_id, miner_id, epoch, wallet_address, reward_urtc,
                status, submitted_at, signature, public_key, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 'approved', ?, 'sig', 'pk', ?, ?)
        """, ("claim-1", "miner-1", 1, "RTC" + "A" * 24, 1000, now, now, now))
        conn.execute("""
            CREATE TABLE rewards_pool (pool_name TEXT PRIMARY KEY, balance_urtc INTEGER)
        """)
        conn.execute("""
            CREATE TABLE claims_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                claim_id TEXT,
                action TEXT,
                actor TEXT,
                details TEXT,
                timestamp INTEGER
            )
        """)
        conn.execute("INSERT INTO rewards_pool VALUES ('epoch_rewards', 1000000)")

    broadcasts = []
    lock = threading.Lock()

    def fake_broadcast(tx_data, _db_path):
        with lock:
            broadcasts.append(tx_data["claim_ids"])
            tx_hash = f"0xtx{len(broadcasts)}"
        return True, tx_hash, None

    monkeypatch.setattr("claims_settlement.sign_and_broadcast_transaction", fake_broadcast)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(
            lambda _: process_claims_batch(
                db_path,
                max_claims=1,
                min_batch_size=1,
                max_wait_seconds=0,
            ),
            range(2),
        ))

    assert len(broadcasts) == 1
    assert sum(1 for result in results if result["processed"]) == 1
    assert sum(1 for result in results if result["success_count"] == 1) == 1

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT status, transaction_hash FROM claims WHERE claim_id = 'claim-1'"
        ).fetchone()
    assert row[0] == "settled"
    assert row[1] == "0xtx1"


def test_process_claims_batch_marks_reserved_claim_failed_when_broadcast_raises(tmp_path, monkeypatch):
    db_path = str(tmp_path / "claims.db")
    now = 1_700_000_000
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE claims (
                claim_id TEXT PRIMARY KEY,
                miner_id TEXT,
                epoch INTEGER,
                wallet_address TEXT,
                reward_urtc INTEGER,
                status TEXT,
                submitted_at INTEGER,
                verified_at INTEGER,
                settled_at INTEGER,
                transaction_hash TEXT,
                settlement_batch TEXT,
                rejection_reason TEXT,
                signature TEXT,
                public_key TEXT,
                ip_address TEXT,
                user_agent TEXT,
                created_at INTEGER,
                updated_at INTEGER,
                UNIQUE(miner_id, epoch)
            )
        """)
        conn.execute("""
            INSERT INTO claims (
                claim_id, miner_id, epoch, wallet_address, reward_urtc,
                status, submitted_at, signature, public_key, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 'approved', ?, 'sig', 'pk', ?, ?)
        """, ("claim-1", "miner-1", 1, "RTC" + "A" * 24, 1000, now, now, now))
        conn.execute("""
            CREATE TABLE rewards_pool (pool_name TEXT PRIMARY KEY, balance_urtc INTEGER)
        """)
        conn.execute("""
            CREATE TABLE claims_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                claim_id TEXT,
                action TEXT,
                actor TEXT,
                details TEXT,
                timestamp INTEGER
            )
        """)
        conn.execute("INSERT INTO rewards_pool VALUES ('epoch_rewards', 1000000)")

    def raising_broadcast(_tx_data, _db_path):
        raise RuntimeError("wallet unavailable")

    monkeypatch.setattr("claims_settlement.sign_and_broadcast_transaction", raising_broadcast)

    result = process_claims_batch(
        db_path,
        max_claims=1,
        min_batch_size=1,
        max_wait_seconds=0,
    )

    assert result["processed"] is False
    assert result["failed_count"] == 1
    assert "wallet unavailable" in result["error"]

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT status, transaction_hash, settlement_batch FROM claims WHERE claim_id = 'claim-1'"
        ).fetchone()
        audit_details = conn.execute(
            "SELECT details FROM claims_audit WHERE claim_id = 'claim-1' AND action = 'claim_failed'"
        ).fetchone()[0]
    assert row[0] == "failed"
    assert row[1] is None
    assert row[2] is not None
    assert "wallet unavailable" in audit_details


def test_settlement_batch_conditions_require_min_size_or_wait():
    now = 1_700_000_100
    fresh_claim = {"claim_id": "claim-1", "submitted_at": now - 10}
    old_claim = {"claim_id": "claim-2", "submitted_at": now - 2_000}

    assert not settlement_batch_conditions_met([fresh_claim], 2, 1_000, now)
    assert settlement_batch_conditions_met([fresh_claim, old_claim], 2, 1_000, now)
    assert settlement_batch_conditions_met([old_claim], 2, 1_000, now)


def test_process_claims_batch_releases_reserved_rows_when_actual_batch_too_small(tmp_path, monkeypatch):
    db_path = str(tmp_path / "claims.db")
    now = 1_700_000_000
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE claims (
                claim_id TEXT PRIMARY KEY,
                miner_id TEXT,
                epoch INTEGER,
                wallet_address TEXT,
                reward_urtc INTEGER,
                status TEXT,
                submitted_at INTEGER,
                verified_at INTEGER,
                settled_at INTEGER,
                transaction_hash TEXT,
                settlement_batch TEXT,
                rejection_reason TEXT,
                signature TEXT,
                public_key TEXT,
                ip_address TEXT,
                user_agent TEXT,
                created_at INTEGER,
                updated_at INTEGER,
                UNIQUE(miner_id, epoch)
            )
        """)
        for idx in range(1, 3):
            conn.execute("""
                INSERT INTO claims (
                    claim_id, miner_id, epoch, wallet_address, reward_urtc,
                    status, submitted_at, signature, public_key, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'approved', ?, 'sig', 'pk', ?, ?)
            """, (
                f"claim-{idx}",
                f"miner-{idx}",
                1,
                "RTC" + ("A" if idx == 1 else "B") * 24,
                1000,
                now,
                now,
                now,
            ))
        conn.execute("CREATE TABLE rewards_pool (pool_name TEXT PRIMARY KEY, balance_urtc INTEGER)")
        conn.execute("INSERT INTO rewards_pool VALUES ('epoch_rewards', 1000000)")

    broadcasts = []

    def reserve_one_claim(_db_path, _max_claims, batch_id):
        with sqlite3.connect(db_path) as conn:
            conn.execute("""
                UPDATE claims
                SET status = 'settling', settlement_batch = ?
                WHERE claim_id = 'claim-1'
            """, (batch_id,))
        return [{
            "claim_id": "claim-1",
            "miner_id": "miner-1",
            "epoch": 1,
            "wallet_address": "RTC" + "A" * 24,
            "reward_urtc": 1000,
            "submitted_at": now,
        }]

    def fake_broadcast(tx_data, _db_path):
        broadcasts.append(tx_data)
        return True, "0xtx", None

    monkeypatch.setattr("claims_settlement.time.time", lambda: now + 10)
    monkeypatch.setattr("claims_settlement.reserve_claims_for_settlement", reserve_one_claim)
    monkeypatch.setattr("claims_settlement.sign_and_broadcast_transaction", fake_broadcast)

    result = process_claims_batch(
        db_path,
        max_claims=2,
        min_batch_size=2,
        max_wait_seconds=1_000,
    )

    assert result["processed"] is False
    assert result["released_count"] == 1
    assert result["error"] == "Batch conditions not met after reservation"
    assert broadcasts == []

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT status, settlement_batch FROM claims WHERE claim_id = 'claim-1'"
        ).fetchone()
    assert row == ("approved", None)
