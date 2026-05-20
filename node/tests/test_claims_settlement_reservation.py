#!/usr/bin/env python3
"""Regression tests for claims settlement reservation safety."""

import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import claims_settlement


def _init_db(path):
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE claims (
                claim_id TEXT PRIMARY KEY,
                miner_id TEXT,
                epoch INTEGER,
                wallet_address TEXT,
                reward_urtc INTEGER,
                submitted_at INTEGER,
                status TEXT,
                settlement_batch TEXT,
                settlement_error TEXT,
                updated_at INTEGER
            );
            CREATE TABLE rewards_pool (
                pool_name TEXT PRIMARY KEY,
                balance_urtc INTEGER
            );
            """
        )


def _insert_claim(path, claim_id, reward_urtc, submitted_at):
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            INSERT INTO claims (
                claim_id, miner_id, epoch, wallet_address, reward_urtc,
                submitted_at, status
            ) VALUES (?, ?, 1, ?, ?, ?, 'approved')
            """,
            (claim_id, f"miner-{claim_id}", f"wallet-{claim_id}", reward_urtc, submitted_at),
        )


def test_insufficient_pool_check_runs_after_reservation_and_releases_batch(tmp_path, monkeypatch):
    db_path = str(tmp_path / "claims.db")
    _init_db(db_path)
    _insert_claim(db_path, "claim-small", 25, 1)
    _insert_claim(db_path, "claim-large", 100, 2)

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO rewards_pool (pool_name, balance_urtc) VALUES ('epoch_rewards', 50)"
        )

    broadcasts = []
    monkeypatch.setattr(
        claims_settlement,
        "sign_and_broadcast_transaction",
        lambda tx_data, db_path: broadcasts.append(tx_data) or (True, "0xabc", None),
    )

    result = claims_settlement.process_claims_batch(
        db_path,
        max_claims=2,
        min_batch_size=1,
        max_wait_seconds=0,
    )

    assert result["processed"] is False
    assert result["error"] == "Insufficient funds: need 1325 (125 claims + 1200 fee), have 50"
    assert result["released_count"] == 2
    assert broadcasts == []

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT status, settlement_batch, settlement_error FROM claims ORDER BY submitted_at"
        ).fetchall()

    assert rows == [
        ("approved", None, "Insufficient funds: need 1325 (125 claims + 1200 fee), have 50"),
        ("approved", None, "Insufficient funds: need 1325 (125 claims + 1200 fee), have 50"),
    ]


def test_post_reservation_pool_check_includes_settlement_fee(tmp_path, monkeypatch):
    db_path = str(tmp_path / "claims.db")
    _init_db(db_path)
    _insert_claim(db_path, "claim-1", 1000, 1)

    with sqlite3.connect(db_path) as conn:
        # The pool covers the claim output but not output + settlement fee
        # (1000 + base 1000 + one output 100 = 2100).
        conn.execute(
            "INSERT INTO rewards_pool (pool_name, balance_urtc) VALUES ('epoch_rewards', 1000)"
        )

    broadcasts = []
    monkeypatch.setattr(
        claims_settlement,
        "sign_and_broadcast_transaction",
        lambda tx_data, db_path: broadcasts.append(tx_data) or (True, "0xabc", None),
    )

    result = claims_settlement.process_claims_batch(
        db_path,
        max_claims=1,
        min_batch_size=1,
        max_wait_seconds=0,
    )

    assert result["processed"] is False
    assert result["error"] == "Insufficient funds: need 2100 (1000 claims + 1100 fee), have 1000"
    assert result["released_count"] == 1
    assert broadcasts == []

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT status, settlement_batch, settlement_error FROM claims WHERE claim_id = 'claim-1'"
        ).fetchone()

    assert row == (
        "approved",
        None,
        "Insufficient funds: need 2100 (1000 claims + 1100 fee), have 1000",
    )
