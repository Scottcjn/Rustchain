#!/usr/bin/env python3
"""
Unit tests verifying that process_claims_batch requires all claims in a batch
to be successfully settled before returning processed = True.
"""

import sys
import os
import sqlite3
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "node"))

from claims_settlement import process_claims_batch


def create_mock_db(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE claims (
            claim_id TEXT PRIMARY KEY,
            miner_id TEXT,
            epoch INTEGER,
            wallet_address TEXT,
            reward_urtc INTEGER,
            status TEXT,
            submitted_at INTEGER,
            settlement_batch TEXT,
            updated_at INTEGER,
            settlement_error TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE rewards_pool (
            pool_name TEXT PRIMARY KEY,
            balance_urtc INTEGER
        )
    """)
    cur.execute("INSERT INTO rewards_pool VALUES ('epoch_rewards', 1000000000)")
    
    # Insert 5 approved claims
    for i in range(1, 6):
        cur.execute("""
            INSERT INTO claims VALUES (
                ?, 'miner_1', 10, 'wallet_1', 1000000, 'approved', 1000, NULL, 1000, NULL
            )
        """, (f"claim_{i}",))
    conn.commit()
    conn.close()


def test_process_claims_batch_requires_full_settlement(tmp_path, monkeypatch):
    db_file = str(tmp_path / "test_node.db")
    create_mock_db(db_file)

    monkeypatch.setenv("TREASURY_KEY_PATH", "/tmp/fake_treasury.pem")
    monkeypatch.setenv("NODE_API_URL", "http://localhost:8000")

    # Mock sign_and_broadcast_transaction to succeed
    import claims_settlement
    monkeypatch.setattr(
        claims_settlement,
        "sign_and_broadcast_transaction",
        lambda tx_data, db_path: (True, "0x123abc456def", None)
    )

    # Mock update_claims_settled to simulate partial failure (only 2 out of 5 updated)
    monkeypatch.setattr(
        claims_settlement,
        "update_claims_settled",
        lambda db_path, claim_ids, tx_hash, batch_id: 2
    )

    result = process_claims_batch(
        db_path=db_file,
        max_claims=5,
        min_batch_size=1,
        max_wait_seconds=0
    )

    # Verify processed is False when settled_count != len(claims_to_process)
    assert result["processed"] is False
    assert result["success_count"] == 2
    assert result["failed_count"] == 3
    assert result["error"] is not None
    assert "Settlement incomplete" in result["error"]


def test_process_claims_batch_success_when_all_settled(tmp_path, monkeypatch):
    db_file = str(tmp_path / "test_node.db")
    create_mock_db(db_file)

    monkeypatch.setenv("TREASURY_KEY_PATH", "/tmp/fake_treasury.pem")
    monkeypatch.setenv("NODE_API_URL", "http://localhost:8000")

    import claims_settlement
    monkeypatch.setattr(
        claims_settlement,
        "sign_and_broadcast_transaction",
        lambda tx_data, db_path: (True, "0x789xyz", None)
    )

    # Mock update_claims_settled to return all 5 settled
    monkeypatch.setattr(
        claims_settlement,
        "update_claims_settled",
        lambda db_path, claim_ids, tx_hash, batch_id: len(claim_ids)
    )

    result = process_claims_batch(
        db_path=db_file,
        max_claims=5,
        min_batch_size=1,
        max_wait_seconds=0
    )

    assert result["processed"] is True
    assert result["success_count"] == 5
    assert result["failed_count"] == 0
    assert result["transaction_hash"] == "0x789xyz"
    assert result["error"] is None
