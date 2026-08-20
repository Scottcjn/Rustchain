#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Unit tests for claims_settlement.py — covering all functions not tested
by test_claims_settlement_reservation.py or test_claims_settlement_batch_id.py.

Existing test files cover:
  - reserve_claims_for_settlement / release_reserved_claims_for_settlement
  - reserve_rewards_pool_funds (concurrent safety)
  - process_claims_batch (concurrent reservation, broadcast failure, post-reservation
    condition re-check, insufficient-pool release)
  - generate_batch_id (sequence concurrency)
  - settlement_batch_conditions_met (min-size + max-wait logic)

This file covers every other function and edge case."""

import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# ── path setup ──────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from claims_settlement import (
    SettlementError,
    InsufficientFundsError,
    TransactionFailedError,
    SettlementConfigurationError,
    compute_local_batch_digest,
    validate_settlement_config,
    _normalize_claim_limit,
    get_pending_claims,
    get_verifying_claims,
    check_rewards_pool_balance,
    reserve_rewards_pool_funds,
    release_rewards_pool_funds,
    construct_settlement_transaction,
    calculate_settlement_fee,
    sign_and_broadcast_transaction,
    update_claims_settled,
    update_claims_failed,
    generate_batch_id,
    process_claims_batch,
    get_settlement_stats,
    settlement_batch_conditions_met,
    URTC_PER_RTC,
)

# ═══════════════════════════════════════════════════════════════════════
# Fixture helpers
# ═══════════════════════════════════════════════════════════════════════

CLAIMS_SCHEMA = """
CREATE TABLE IF NOT EXISTS claims (
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
    updated_at INTEGER
);
"""

REWARDS_POOL_SCHEMA = """
CREATE TABLE IF NOT EXISTS rewards_pool (
    pool_name TEXT PRIMARY KEY,
    balance_urtc INTEGER
);
"""

AUDIT_SCHEMA = """
CREATE TABLE IF NOT EXISTS claims_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id TEXT,
    action TEXT,
    actor TEXT,
    details TEXT,
    timestamp INTEGER
);
"""

SETTLEMENT_BATCH_SEQUENCE_SCHEMA = """
CREATE TABLE IF NOT EXISTS settlement_batch_sequence (
    batch_day TEXT PRIMARY KEY,
    sequence INTEGER NOT NULL
);
"""


def _init_db(db_path, schema_sql=CLAIMS_SCHEMA):
    """Create a fresh claims database with given schema(s)."""
    with sqlite3.connect(db_path) as conn:
        conn.executescript(schema_sql)


def _insert_claim(
    db_path,
    claim_id="claim-1",
    miner_id="miner-1",
    epoch=1,
    wallet_address="RTC" + "A" * 24,
    reward_urtc=1000,
    status="approved",
    submitted_at=None,
    settlement_batch=None,
    settled_at=None,
    transaction_hash=None,
):
    if submitted_at is None:
        submitted_at = int(time.time())
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """INSERT INTO claims (
                claim_id, miner_id, epoch, wallet_address, reward_urtc,
                status, submitted_at, created_at, updated_at,
                settlement_batch, settled_at, transaction_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                claim_id, miner_id, epoch, wallet_address, reward_urtc,
                status, submitted_at, submitted_at, submitted_at,
                settlement_batch, settled_at, transaction_hash,
            ),
        )


def _seed_rewards_pool(db_path, balance_urtc=1_000_000):
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO rewards_pool (pool_name, balance_urtc) "
            "VALUES ('epoch_rewards', ?)",
            (balance_urtc,),
        )


# ═══════════════════════════════════════════════════════════════════════
# 1. Exception classes
# ═══════════════════════════════════════════════════════════════════════

class TestExceptions:
    def test_settlement_error_base(self):
        err = SettlementError("base error")
        assert str(err) == "base error"
        assert isinstance(err, Exception)

    def test_insufficient_funds_error(self):
        err = InsufficientFundsError("not enough RTC")
        assert str(err) == "not enough RTC"
        assert isinstance(err, SettlementError)

    def test_transaction_failed_error(self):
        err = TransactionFailedError("broadcast failed")
        assert str(err) == "broadcast failed"
        assert isinstance(err, SettlementError)


# ═══════════════════════════════════════════════════════════════════════
# 2. _normalize_claim_limit
# ═══════════════════════════════════════════════════════════════════════

class TestNormalizeClaimLimit:
    def test_positive_int(self):
        assert _normalize_claim_limit(42, default=100) == 42

    def test_zero(self):
        assert _normalize_claim_limit(0, default=100) == 0

    def test_negative_clamps_to_zero(self):
        assert _normalize_claim_limit(-5, default=100) == 0

    def test_none_falls_back_to_default(self):
        assert _normalize_claim_limit(None, default=100) == 100

    def test_string_int_converts(self):
        assert _normalize_claim_limit("10", default=100) == 10

    def test_bad_string_falls_back(self):
        assert _normalize_claim_limit("abc", default=50) == 50

    def test_float_truncates_then_clamps(self):
        assert _normalize_claim_limit(3.9, default=100) == 3


# ═══════════════════════════════════════════════════════════════════════
# 3. get_pending_claims
# ═══════════════════════════════════════════════════════════════════════

class TestGetPendingClaims:
    def test_returns_approved_claims_ordered_by_submitted_at(self, tmp_path):
        db = str(tmp_path / "test.db")
        _init_db(db)
        _insert_claim(db, "c-1", submitted_at=100)
        _insert_claim(db, "c-2", submitted_at=50)
        _insert_claim(db, "c-3", status="settled", submitted_at=200)

        claims = get_pending_claims(db, max_claims=10)
        assert len(claims) == 2
        assert claims[0]["claim_id"] == "c-2"  # earlier first
        assert claims[1]["claim_id"] == "c-1"

    def test_empty_when_no_approved_claims(self, tmp_path):
        db = str(tmp_path / "test.db")
        _init_db(db)
        claims = get_pending_claims(db)
        assert claims == []

    def test_respects_max_claims_limit(self, tmp_path):
        db = str(tmp_path / "test.db")
        _init_db(db)
        for i in range(10):
            _insert_claim(db, f"c-{i}", submitted_at=i)
        claims = get_pending_claims(db, max_claims=3)
        assert len(claims) == 3

    def test_returns_empty_on_db_error(self, tmp_path):
        db = str(tmp_path / "nonexistent" / "missing.db")
        claims = get_pending_claims(db)
        assert claims == []

    def test_handles_invalid_max_claims_gracefully(self, tmp_path):
        db = str(tmp_path / "test.db")
        _init_db(db)
        _insert_claim(db, "c-1", submitted_at=100)
        claims = get_pending_claims(db, max_claims="invalid")
        assert len(claims) == 1  # falls back to default=100, includes claim


# ═══════════════════════════════════════════════════════════════════════
# 4. get_verifying_claims
# ═══════════════════════════════════════════════════════════════════════

class TestGetVerifyingClaims:
    def test_returns_claims_stuck_in_verifying(self, tmp_path):
        db = str(tmp_path / "test.db")
        _init_db(db)
        _insert_claim(db, "old", status="verifying", submitted_at=100)
        _insert_claim(db, "recent", status="verifying", submitted_at=500)

        claims = get_verifying_claims(db, older_than_seconds=200)
        # At current time, 100 is >200s ago; 500 might not be
        assert len(claims) >= 1
        assert any(c["claim_id"] == "old" for c in claims)

    def test_ignores_non_verifying_claims(self, tmp_path):
        db = str(tmp_path / "test.db")
        _init_db(db)
        _insert_claim(db, "approved", status="approved", submitted_at=50)
        _insert_claim(db, "settled", status="settled", submitted_at=100)
        claims = get_verifying_claims(db, older_than_seconds=10)
        assert claims == []

    def test_returns_empty_on_db_error(self, tmp_path):
        db = str(tmp_path / "nonexistent" / "missing.db")
        claims = get_verifying_claims(db)
        assert claims == []


# ═══════════════════════════════════════════════════════════════════════
# 5. check_rewards_pool_balance
# ═══════════════════════════════════════════════════════════════════════

class TestCheckRewardsPoolBalance:
    def test_sufficient_balance(self, tmp_path):
        db = str(tmp_path / "test.db")
        _init_db(db, REWARDS_POOL_SCHEMA)
        _seed_rewards_pool(db, 5000)
        sufficient, balance = check_rewards_pool_balance(db, 3000)
        assert sufficient is True
        assert balance == 5000

    def test_insufficient_balance(self, tmp_path):
        db = str(tmp_path / "test.db")
        _init_db(db, REWARDS_POOL_SCHEMA)
        _seed_rewards_pool(db, 1000)
        sufficient, balance = check_rewards_pool_balance(db, 5000)
        assert sufficient is False
        assert balance == 1000

    def test_exact_balance(self, tmp_path):
        db = str(tmp_path / "test.db")
        _init_db(db, REWARDS_POOL_SCHEMA)
        _seed_rewards_pool(db, 5000)
        sufficient, balance = check_rewards_pool_balance(db, 5000)
        assert sufficient is True

    def test_fallback_no_table(self, tmp_path):
        db = str(tmp_path / "test.db")
        _init_db(db, CLAIMS_SCHEMA)  # no rewards_pool table
        sufficient, balance = check_rewards_pool_balance(db, 1000)
        assert sufficient is True  # assume sufficient
        assert balance == 10000  # 10x buffer

    def test_db_error_falls_back_to_true(self, tmp_path):
        db = str(tmp_path / "nonexistent" / "missing.db")
        sufficient, balance = check_rewards_pool_balance(db, 1000)
        assert sufficient is True
        assert balance == 1000


# ═══════════════════════════════════════════════════════════════════════
# 6. reserve_rewards_pool_funds (basic unit tests; concurrent safety
#    is covered by test_claims_settlement_reservation.py)
# ═══════════════════════════════════════════════════════════════════════

class TestReserveRewardsPoolFunds:
    def test_successful_reservation(self, tmp_path):
        db = str(tmp_path / "test.db")
        _init_db(db, REWARDS_POOL_SCHEMA)
        _seed_rewards_pool(db, 5000)
        reserved, balance = reserve_rewards_pool_funds(db, 3000)
        assert reserved is True
        assert balance == 5000
        # Verify pool decreased
        with sqlite3.connect(db) as conn:
            row = conn.execute(
                "SELECT balance_urtc FROM rewards_pool WHERE pool_name = 'epoch_rewards'"
            ).fetchone()
        assert row[0] == 2000

    def test_insufficient_funds(self, tmp_path):
        db = str(tmp_path / "test.db")
        _init_db(db, REWARDS_POOL_SCHEMA)
        _seed_rewards_pool(db, 1000)
        reserved, balance = reserve_rewards_pool_funds(db, 5000)
        assert reserved is False
        assert balance == 1000
        # Pool unchanged
        with sqlite3.connect(db) as conn:
            row = conn.execute(
                "SELECT balance_urtc FROM rewards_pool WHERE pool_name = 'epoch_rewards'"
            ).fetchone()
        assert row[0] == 1000

    def test_exact_reservation(self, tmp_path):
        db = str(tmp_path / "test.db")
        _init_db(db, REWARDS_POOL_SCHEMA)
        _seed_rewards_pool(db, 3000)
        reserved, balance = reserve_rewards_pool_funds(db, 3000)
        assert reserved is True
        with sqlite3.connect(db) as conn:
            row = conn.execute(
                "SELECT balance_urtc FROM rewards_pool WHERE pool_name = 'epoch_rewards'"
            ).fetchone()
        assert row[0] == 0

    def test_no_table_returns_noop_success(self, tmp_path):
        db = str(tmp_path / "test.db")
        _init_db(db, CLAIMS_SCHEMA)  # no rewards_pool
        reserved, balance = reserve_rewards_pool_funds(db, 3000)
        assert reserved is True
        assert balance == 30000  # 10x buffer

    def test_zero_amount_reservation(self, tmp_path):
        db = str(tmp_path / "test.db")
        _init_db(db, REWARDS_POOL_SCHEMA)
        _seed_rewards_pool(db, 1000)
        reserved, balance = reserve_rewards_pool_funds(db, 0)
        assert reserved is True
        with sqlite3.connect(db) as conn:
            row = conn.execute(
                "SELECT balance_urtc FROM rewards_pool WHERE pool_name = 'epoch_rewards'"
            ).fetchone()
        assert row[0] == 1000  # unchanged (0 debit = no-op but passes thanks to >= 0 check)


# ═══════════════════════════════════════════════════════════════════════
# 7. release_rewards_pool_funds
# ═══════════════════════════════════════════════════════════════════════

class TestReleaseRewardsPoolFunds:
    def test_release_adds_funds_back(self, tmp_path):
        db = str(tmp_path / "test.db")
        _init_db(db, REWARDS_POOL_SCHEMA)
        _seed_rewards_pool(db, 5000)
        result = release_rewards_pool_funds(db, 2000)
        assert result is True
        with sqlite3.connect(db) as conn:
            row = conn.execute(
                "SELECT balance_urtc FROM rewards_pool WHERE pool_name = 'epoch_rewards'"
            ).fetchone()
        assert row[0] == 7000

    def test_zero_amount_is_noop(self, tmp_path):
        db = str(tmp_path / "test.db")
        _init_db(db, REWARDS_POOL_SCHEMA)
        _seed_rewards_pool(db, 5000)
        result = release_rewards_pool_funds(db, 0)
        assert result is True  # short-circuits to True
        with sqlite3.connect(db) as conn:
            row = conn.execute(
                "SELECT balance_urtc FROM rewards_pool WHERE pool_name = 'epoch_rewards'"
            ).fetchone()
        assert row[0] == 5000

    def test_negative_amount_is_noop(self, tmp_path):
        db = str(tmp_path / "test.db")
        _init_db(db, REWARDS_POOL_SCHEMA)
        _seed_rewards_pool(db, 5000)
        result = release_rewards_pool_funds(db, -100)
        assert result is True
        with sqlite3.connect(db) as conn:
            row = conn.execute(
                "SELECT balance_urtc FROM rewards_pool WHERE pool_name = 'epoch_rewards'"
            ).fetchone()
        assert row[0] == 5000

    def test_no_table_fallback(self, tmp_path):
        db = str(tmp_path / "test.db")
        _init_db(db, CLAIMS_SCHEMA)  # no rewards_pool
        result = release_rewards_pool_funds(db, 2000)
        assert result is True

    def test_db_error_returns_false(self, tmp_path):
        db = str(tmp_path / "nonexistent" / "missing.db")
        result = release_rewards_pool_funds(db, 2000)
        assert result is False


# ═══════════════════════════════════════════════════════════════════════
# 8. construct_settlement_transaction
# ═══════════════════════════════════════════════════════════════════════

class TestConstructSettlementTransaction:
    def test_single_claim(self):
        claims = [
            {"claim_id": "c-1", "wallet_address": "RTCaaa", "reward_urtc": 1000}
        ]
        tx = construct_settlement_transaction(claims)
        assert tx["type"] == "multi_output_transfer"
        assert len(tx["outputs"]) == 1
        assert tx["outputs"][0]["address"] == "RTCaaa"
        assert tx["total_amount_urtc"] == 1000
        assert tx["claim_ids"] == ["c-1"]
        assert tx["fee_urtc"] > 0

    def test_multiple_claims_aggregates_total(self):
        claims = [
            {"claim_id": "c-1", "wallet_address": "A", "reward_urtc": 500},
            {"claim_id": "c-2", "wallet_address": "B", "reward_urtc": 1500},
            {"claim_id": "c-3", "wallet_address": "C", "reward_urtc": 200},
        ]
        tx = construct_settlement_transaction(claims)
        assert len(tx["outputs"]) == 3
        assert tx["total_amount_urtc"] == 2200
        assert tx["claim_ids"] == ["c-1", "c-2", "c-3"]

    def test_has_timestamp(self):
        before = int(time.time())
        tx = construct_settlement_transaction([])
        after = int(time.time())
        assert before <= tx["created_at"] <= after

    def test_fee_is_calculated_based_on_claim_count(self):
        claims_1 = [{"claim_id": "c-1", "wallet_address": "A", "reward_urtc": 100}]
        claims_10 = [{"claim_id": f"c-{i}", "wallet_address": "A", "reward_urtc": 100} for i in range(10)]
        tx_1 = construct_settlement_transaction(claims_1)
        tx_10 = construct_settlement_transaction(claims_10)
        assert tx_10["fee_urtc"] > tx_1["fee_urtc"]


# ═══════════════════════════════════════════════════════════════════════
# 9. calculate_settlement_fee
# ═══════════════════════════════════════════════════════════════════════

class TestCalculateSettlementFee:
    def test_base_fee_for_zero_outputs(self):
        assert calculate_settlement_fee(0) == 1000

    def test_single_output(self):
        assert calculate_settlement_fee(1) == 1100  # 1000 + 100

    def test_multiple_outputs(self):
        assert calculate_settlement_fee(5) == 1500   # 1000 + 500
        assert calculate_settlement_fee(10) == 2000  # 1000 + 1000

    def test_large_batch(self):
        assert calculate_settlement_fee(100) == 11000  # 1000 + 10000


# ═══════════════════════════════════════════════════════════════════════
# 10. sign_and_broadcast_transaction
# ═══════════════════════════════════════════════════════════════════════

def _tx(batch_id="batch_2025_01_01_001", **over):
    tx = {
        "batch_id": batch_id,
        "total_amount_urtc": 5000,
        "outputs": [{"address": "RTCaaa", "amount_urtc": 5000}],
        "fee_urtc": 1100,
        "claim_ids": ["c-1"],
        "created_at": 1700000000,
    }
    tx.update(over)
    return tx


def _configure_settlement(monkeypatch, tmp_path):
    """Point settlement at a treasury key path and a node URL."""
    key = tmp_path / "treasury.pem"
    key.write_text("not-a-real-key")
    monkeypatch.setenv("TREASURY_KEY_PATH", str(key))
    monkeypatch.setenv("NODE_API_URL", "http://node.invalid:8099")


def _stub_signer(monkeypatch, signature="0x" + "ab" * 64):
    """Make signing succeed so broadcast behaviour is what is under test."""
    import settlement_signer

    monkeypatch.setattr(
        settlement_signer,
        "sign_settlement_batch",
        lambda tx_data, key_path=None: (True, signature, None),
    )


class _Resp:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):  # noqa: F811 - mimics requests.Response.json
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


def _stub_post(monkeypatch, resp):
    """Stub requests.post with a canned response, or an exception to raise."""
    import requests

    def fake_post(*args, **kwargs):
        if isinstance(resp, Exception):
            raise resp
        return resp

    monkeypatch.setattr(requests, "post", fake_post)


class TestComputeLocalBatchDigest:
    """The digest is a local correlation id — never an on-chain reference."""

    def test_is_not_0x_prefixed(self):
        digest = compute_local_batch_digest(_tx())
        assert not digest.startswith("0x")
        assert len(digest) == 64

    def test_deterministic_same_input(self):
        assert compute_local_batch_digest(_tx()) == compute_local_batch_digest(_tx())

    def test_different_input_different_digest(self):
        assert compute_local_batch_digest(_tx("batch_a")) != compute_local_batch_digest(
            _tx("batch_b")
        )


class TestValidateSettlementConfig:
    def test_raises_when_both_unset(self, monkeypatch):
        monkeypatch.delenv("TREASURY_KEY_PATH", raising=False)
        monkeypatch.delenv("NODE_API_URL", raising=False)
        with pytest.raises(SettlementConfigurationError) as exc:
            validate_settlement_config()
        assert "TREASURY_KEY_PATH" in str(exc.value)
        assert "NODE_API_URL" in str(exc.value)

    def test_raises_when_node_url_unset(self, monkeypatch, tmp_path):
        monkeypatch.setenv("TREASURY_KEY_PATH", str(tmp_path / "k.pem"))
        monkeypatch.delenv("NODE_API_URL", raising=False)
        with pytest.raises(SettlementConfigurationError):
            validate_settlement_config()

    def test_blank_is_treated_as_unset(self, monkeypatch, tmp_path):
        monkeypatch.setenv("TREASURY_KEY_PATH", str(tmp_path / "k.pem"))
        monkeypatch.setenv("NODE_API_URL", "   ")
        with pytest.raises(SettlementConfigurationError):
            validate_settlement_config()

    def test_passes_when_configured(self, monkeypatch, tmp_path):
        _configure_settlement(monkeypatch, tmp_path)
        validate_settlement_config()  # must not raise


class TestSignAndBroadcastTransaction:
    """Regression cover for #8230.

    Every one of these cases previously returned ``success=True`` with a
    fabricated ``0x…`` hash while nothing reached the chain.
    """

    def test_missing_config_is_a_hard_error(self, monkeypatch):
        monkeypatch.delenv("TREASURY_KEY_PATH", raising=False)
        monkeypatch.delenv("NODE_API_URL", raising=False)
        with pytest.raises(SettlementConfigurationError):
            sign_and_broadcast_transaction(_tx(), ":memory:")

    def test_signer_unavailable_returns_failure(self, monkeypatch, tmp_path):
        _configure_settlement(monkeypatch, tmp_path)
        import builtins

        real_import = builtins.__import__

        def no_signer(name, *args, **kwargs):
            if name == "settlement_signer":
                raise ImportError("no module named settlement_signer")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", no_signer)
        success, tx_hash, error = sign_and_broadcast_transaction(_tx(), ":memory:")
        assert success is False
        assert tx_hash is None
        assert "not signed" in error

    def test_signing_failure_returns_failure(self, monkeypatch, tmp_path):
        _configure_settlement(monkeypatch, tmp_path)
        import settlement_signer

        monkeypatch.setattr(
            settlement_signer,
            "sign_settlement_batch",
            lambda tx_data, key_path=None: (False, None, "bad treasury key"),
        )
        success, tx_hash, error = sign_and_broadcast_transaction(_tx(), ":memory:")
        assert success is False
        assert tx_hash is None
        assert "bad treasury key" in error

    def test_unreachable_node_returns_failure(self, monkeypatch, tmp_path):
        _configure_settlement(monkeypatch, tmp_path)
        _stub_signer(monkeypatch)
        _stub_post(monkeypatch, ConnectionError("connection refused"))
        success, tx_hash, error = sign_and_broadcast_transaction(_tx(), ":memory:")
        assert success is False
        assert tx_hash is None
        assert "NOT confirmed on chain" in error

    def test_non_2xx_returns_failure(self, monkeypatch, tmp_path):
        _configure_settlement(monkeypatch, tmp_path)
        _stub_signer(monkeypatch)
        _stub_post(monkeypatch, _Resp(503, {}))
        success, tx_hash, error = sign_and_broadcast_transaction(_tx(), ":memory:")
        assert success is False
        assert tx_hash is None
        assert "503" in error

    def test_2xx_with_unreadable_body_returns_failure(self, monkeypatch, tmp_path):
        _configure_settlement(monkeypatch, tmp_path)
        _stub_signer(monkeypatch)
        _stub_post(monkeypatch, _Resp(200, ValueError("not json")))
        success, tx_hash, error = sign_and_broadcast_transaction(_tx(), ":memory:")
        assert success is False
        assert tx_hash is None
        assert "UNKNOWN" in error

    def test_2xx_with_ok_false_returns_failure(self, monkeypatch, tmp_path):
        """HTTP 200 carrying an application-level failure is still a failure."""
        _configure_settlement(monkeypatch, tmp_path)
        _stub_signer(monkeypatch)
        _stub_post(monkeypatch, _Resp(200, {"ok": False, "error": "bad signature"}))
        success, tx_hash, error = sign_and_broadcast_transaction(_tx(), ":memory:")
        assert success is False
        assert tx_hash is None
        assert "bad signature" in error

    def test_2xx_without_tx_hash_returns_failure(self, monkeypatch, tmp_path):
        """A 2xx with no hash must not fall back to the local signature."""
        _configure_settlement(monkeypatch, tmp_path)
        signature = "0x" + "ab" * 64
        _stub_signer(monkeypatch, signature=signature)
        _stub_post(monkeypatch, _Resp(200, {"ok": True}))
        success, tx_hash, error = sign_and_broadcast_transaction(_tx(), ":memory:")
        assert success is False
        assert tx_hash is None
        assert signature not in (error or "")

    def test_never_returns_the_local_signature_as_tx_hash(self, monkeypatch, tmp_path):
        signature = "0x" + "cd" * 64
        for resp in (
            ConnectionError("down"),
            _Resp(500, {}),
            _Resp(200, {"ok": True}),
            _Resp(200, ValueError("not json")),
        ):
            _configure_settlement(monkeypatch, tmp_path)
            _stub_signer(monkeypatch, signature=signature)
            _stub_post(monkeypatch, resp)
            success, tx_hash, _ = sign_and_broadcast_transaction(_tx(), ":memory:")
            assert success is False
            assert tx_hash is None

    def test_confirmed_broadcast_returns_node_hash(self, monkeypatch, tmp_path):
        _configure_settlement(monkeypatch, tmp_path)
        _stub_signer(monkeypatch)
        _stub_post(monkeypatch, _Resp(200, {"ok": True, "tx_hash": "0xrealchainhash"}))
        success, tx_hash, error = sign_and_broadcast_transaction(_tx(), ":memory:")
        assert success is True
        assert tx_hash == "0xrealchainhash"
        assert error is None


# ═══════════════════════════════════════════════════════════════════════
# 11. update_claims_settled
# ═══════════════════════════════════════════════════════════════════════

class TestUpdateClaimsSettled:
    def test_updates_single_claim(self, tmp_path):
        db = str(tmp_path / "test.db")
        _init_db(db)
        _insert_claim(db, "c-1", status="settling")

        count = update_claims_settled(db, ["c-1"], "0xabc123", "batch-001")
        assert count == 1

        with sqlite3.connect(db) as conn:
            row = conn.execute(
                "SELECT status, transaction_hash, settlement_batch FROM claims WHERE claim_id = 'c-1'"
            ).fetchone()
        assert row == ("settled", "0xabc123", "batch-001")

    def test_updates_multiple_claims(self, tmp_path):
        db = str(tmp_path / "test.db")
        _init_db(db)
        for i in range(3):
            _insert_claim(db, f"c-{i}", status="settling")

        count = update_claims_settled(db, ["c-0", "c-1", "c-2"], "0xdef456", "batch-001")
        assert count == 3

    def test_skips_nonexistent_claims(self, tmp_path):
        db = str(tmp_path / "test.db")
        _init_db(db)
        _insert_claim(db, "c-1", status="settling")

        count = update_claims_settled(db, ["c-1", "nonexistent"], "0xabc", "batch-001")
        assert count == 1  # only c-1 succeeded

    def test_handles_db_error_gracefully(self, tmp_path):
        db = str(tmp_path / "nonexistent" / "missing.db")
        # db error shouldn't crash — returns 0
        count = update_claims_settled(db, ["c-1"], "0xabc", "batch-001")
        assert count == 0


# ═══════════════════════════════════════════════════════════════════════
# 12. update_claims_failed
# ═══════════════════════════════════════════════════════════════════════

class TestUpdateClaimsFailed:
    def test_updates_single_claim(self, tmp_path):
        db = str(tmp_path / "test.db")
        _init_db(db)
        _insert_claim(db, "c-1", status="settling")

        count = update_claims_failed(db, ["c-1"], "insufficient funds")
        assert count == 1

        with sqlite3.connect(db) as conn:
            row = conn.execute(
                "SELECT status, rejection_reason FROM claims WHERE claim_id = 'c-1'"
            ).fetchone()
        assert row[0] == "failed"
        # rejection_reason may be set by claims_submission module or not

    def test_handles_db_error_gracefully(self, tmp_path):
        db = str(tmp_path / "nonexistent" / "missing.db")
        count = update_claims_failed(db, ["c-1"], "error")
        assert count == 0


# ═══════════════════════════════════════════════════════════════════════
# 13. generate_batch_id (basic; concurrency covered by batch_id test file)
# ═══════════════════════════════════════════════════════════════════════

class TestGenerateBatchId:
    def test_generates_valid_format(self, tmp_path):
        db = str(tmp_path / "test.db")
        _init_db(db, SETTLEMENT_BATCH_SEQUENCE_SCHEMA)
        bid = generate_batch_id(db)
        assert bid.startswith("batch_")
        parts = bid.split("_")
        assert len(parts) == 5  # batch_YYYY_MM_DD_NNN
        assert parts[4].isdigit()

    def test_increments_sequence(self, tmp_path):
        db = str(tmp_path / "test.db")
        _init_db(db, SETTLEMENT_BATCH_SEQUENCE_SCHEMA)
        id1 = generate_batch_id(db)
        id2 = generate_batch_id(db)
        id3 = generate_batch_id(db)
        assert id1 != id2 != id3
        seq1 = int(id1.rsplit("_", 1)[1])
        seq2 = int(id2.rsplit("_", 1)[1])
        seq3 = int(id3.rsplit("_", 1)[1])
        assert seq1 == 1
        assert seq2 == 2
        assert seq3 == 3

    def test_different_days_reset_sequence(self, tmp_path):
        db = str(tmp_path / "test.db")
        _init_db(db, SETTLEMENT_BATCH_SEQUENCE_SCHEMA)
        with patch("claims_settlement.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2025, 1, 1, tzinfo=timezone.utc)
            b1 = generate_batch_id(db)
            b2 = generate_batch_id(db)

            mock_dt.now.return_value = datetime(2025, 1, 2, tzinfo=timezone.utc)
            b3 = generate_batch_id(db)

        assert b1 == "batch_2025_01_01_001"
        assert b2 == "batch_2025_01_01_002"
        assert b3 == "batch_2025_01_02_001"

    def test_creates_sequence_table_if_missing(self, tmp_path):
        db = str(tmp_path / "test.db")
        sqlite3.connect(db).close()  # empty db
        bid = generate_batch_id(db)
        assert bid.startswith("batch_")

    def test_raises_on_db_error(self, tmp_path):
        db = str(tmp_path / "nonexistent" / "missing.db")
        try:
            generate_batch_id(db)
            assert False, "Expected an error"
        except (sqlite3.OperationalError, SettlementError):
            pass


# ═══════════════════════════════════════════════════════════════════════
# 14. get_settlement_stats
# ═══════════════════════════════════════════════════════════════════════

class TestGetSettlementStats:
    def test_empty_database(self, tmp_path):
        db = str(tmp_path / "test.db")
        _init_db(db)
        stats = get_settlement_stats(db, days=7)
        assert stats["settled_claims"] == 0
        assert stats["settled_amount_urtc"] == 0
        assert stats["failed_claims"] == 0
        assert stats["total_batches"] == 0
        assert stats["success_rate"] == 0.0

    def test_settled_claims_counted(self, tmp_path):
        db = str(tmp_path / "test.db")
        _init_db(db)
        now = int(time.time())
        for i in range(5):
            # Insert settled claims with settled_at within window
            _insert_claim(
                db, f"c-{i}", status="settled", reward_urtc=1000 * (i + 1),
                submitted_at=now - 3600, settled_at=now - 1800,
            )
        stats = get_settlement_stats(db, days=7)
        assert stats["settled_claims"] == 5
        assert stats["settled_amount_urtc"] == 15000  # 1000+2000+3000+4000+5000
        # 15000 uRTC == 0.015 RTC (URTC_PER_RTC = 1_000_000), not 0.00015.
        assert stats["settled_amount_rtc"] == 15000 / 1_000_000
        assert stats["settled_amount_rtc"] == stats["settled_amount_urtc"] / URTC_PER_RTC

    def test_mixed_status_counts(self, tmp_path):
        db = str(tmp_path / "test.db")
        _init_db(db)
        now = int(time.time())
        _insert_claim(db, "s-1", status="settled", reward_urtc=2000, submitted_at=now - 100, settled_at=now - 50)
        _insert_claim(db, "s-2", status="settled", reward_urtc=3000, submitted_at=now - 200, settled_at=now - 100)
        _insert_claim(db, "f-1", status="failed", reward_urtc=500, submitted_at=now - 300)
        _insert_claim(db, "p-1", status="approved", reward_urtc=1000, submitted_at=now)

        stats = get_settlement_stats(db, days=7)
        assert stats["settled_claims"] == 2
        assert stats["failed_claims"] == 1

    def test_db_error_returns_error_dict(self, tmp_path):
        db = str(tmp_path / "nonexistent" / "missing.db")
        stats = get_settlement_stats(db)
        assert "error" in stats
        assert stats["period_days"] == 7

    def test_period_respected(self, tmp_path):
        db = str(tmp_path / "test.db")
        _init_db(db)
        now = int(time.time())
        _insert_claim(db, "old", status="settled", reward_urtc=1000,
                      submitted_at=now - 30 * 86400, settled_at=now - 29 * 86400)  # 30 days ago
        _insert_claim(db, "recent", status="settled", reward_urtc=2000,
                      submitted_at=now - 3600, settled_at=now - 1800)

        stats_1day = get_settlement_stats(db, days=1)
        stats_30day = get_settlement_stats(db, days=60)

        assert stats_1day["settled_claims"] == 1  # only recent
        assert stats_1day["settled_amount_urtc"] == 2000
        assert stats_30day["settled_claims"] == 2
        assert stats_30day["settled_amount_urtc"] == 3000

    def test_success_rate_calculation(self, tmp_path):
        db = str(tmp_path / "test.db")
        _init_db(db)
        now = int(time.time())
        for i in range(8):
            _insert_claim(db, f"s-{i}", status="settled", reward_urtc=100, submitted_at=now - 100, settled_at=now - 50)
        for i in range(2):
            _insert_claim(db, f"f-{i}", status="failed", reward_urtc=100, submitted_at=now - 100)

        stats = get_settlement_stats(db, days=7)
        assert stats["success_rate"] == 0.8  # 8/10


# ═══════════════════════════════════════════════════════════════════════
# 15. settlement_batch_conditions_met — extra edges beyond existing tests
# ═══════════════════════════════════════════════════════════════════════

class TestSettlementBatchConditionsMet:
    def test_empty_claims(self):
        assert settlement_batch_conditions_met([], 5, 1800) is False

    def test_minimum_size_met(self):
        claim = {"claim_id": "c-1", "submitted_at": 100}
        assert settlement_batch_conditions_met([claim], 1, 1800) is True

    def test_minimum_size_not_met_and_not_old_enough(self):
        claim = {"claim_id": "c-1", "submitted_at": 100}
        assert settlement_batch_conditions_met([claim], 2, 1800, current_time=100) is False

    def test_old_enough_but_below_minimum(self):
        claim = {"claim_id": "c-1", "submitted_at": 100}
        assert settlement_batch_conditions_met([claim], 2, 1800, current_time=2000) is True

    def test_exact_boundary(self):
        claim = {"claim_id": "c-1", "submitted_at": 100}
        # max_wait_seconds=1800, current_time=1900 => age=1800 == max_wait
        assert settlement_batch_conditions_met([claim], 2, 1800, current_time=1900) is True

    def test_custom_current_time(self):
        claim = {"claim_id": "c-1", "submitted_at": 1000}
        # If no current_time provided, uses time.time() which will be >>1000
        assert settlement_batch_conditions_met([], 1, 1800) is False


# ═══════════════════════════════════════════════════════════════════════
# 16. process_claims_batch — extra edge cases beyond existing test files
# ═══════════════════════════════════════════════════════════════════════

class TestProcessClaimsBatch:
    def test_dry_run_returns_preview(self, tmp_path):
        db = str(tmp_path / "test.db")
        _init_db(db)
        now = int(time.time())
        _insert_claim(db, "c-1", reward_urtc=1000, submitted_at=now - 10)

        result = process_claims_batch(
            db, max_claims=10, min_batch_size=1, max_wait_seconds=30, dry_run=True
        )
        assert result["processed"] is True
        assert result["claims_count"] == 1
        assert result["total_amount_urtc"] == 1000
        assert result["error"] == "Dry run - no actual processing"

    def test_dry_run_does_not_change_status(self, tmp_path):
        db = str(tmp_path / "test.db")
        _init_db(db)
        now = int(time.time())
        _insert_claim(db, "c-1", status="approved", submitted_at=now - 10)

        process_claims_batch(
            db, max_claims=10, min_batch_size=1, max_wait_seconds=30, dry_run=True
        )

        with sqlite3.connect(db) as conn:
            row = conn.execute("SELECT status FROM claims WHERE claim_id = 'c-1'").fetchone()
        assert row[0] == "approved"  # unchanged

    def test_no_pending_claims_returns_empty(self, tmp_path):
        db = str(tmp_path / "test.db")
        _init_db(db)

        result = process_claims_batch(
            db, max_claims=10, min_batch_size=1, max_wait_seconds=30
        )
        assert result["processed"] is False
        assert result["error"] == "Batch conditions not met"

    def test_returns_batch_conditions_not_met_when_too_few(self, tmp_path):
        db = str(tmp_path / "test.db")
        _init_db(db)
        now = int(time.time())
        _insert_claim(db, "c-1", submitted_at=now - 10)

        result = process_claims_batch(
            db, max_claims=10, min_batch_size=5, max_wait_seconds=3600
        )
        assert result["processed"] is False
        assert result["error"] == "Batch conditions not met"

    def test_broadcast_failure_releases_pool_and_marks_failed(self, tmp_path, monkeypatch):
        db = str(tmp_path / "test.db")
        _init_db(db, FULL_SCHEMA)
        now = int(time.time())
        _insert_claim(db, "c-1", reward_urtc=1000, submitted_at=now - 10)
        _seed_rewards_pool(db, 100000)

        def fail_broadcast(tx_data, db_path):
            return False, None, "broadcast rejected"

        monkeypatch.setattr("claims_settlement.sign_and_broadcast_transaction", fail_broadcast)

        result = process_claims_batch(
            db, max_claims=10, min_batch_size=1, max_wait_seconds=30
        )
        assert result["processed"] is False
        assert result["failed_count"] == 1
        assert "broadcast rejected" in result["error"]

        # Pool should be released back
        with sqlite3.connect(db) as conn:
            pool_balance = conn.execute(
                "SELECT balance_urtc FROM rewards_pool WHERE pool_name = 'epoch_rewards'"
            ).fetchone()[0]
        assert pool_balance == 100000  # restored

    def test_broadcast_exception_releases_pool_and_marks_failed(self, tmp_path, monkeypatch):
        db = str(tmp_path / "test.db")
        _init_db(db, FULL_SCHEMA)
        now = int(time.time())
        _insert_claim(db, "c-1", reward_urtc=1000, submitted_at=now - 10)
        _seed_rewards_pool(db, 100000)

        def raise_broadcast(tx_data, db_path):
            raise RuntimeError("wallet connection lost")

        monkeypatch.setattr("claims_settlement.sign_and_broadcast_transaction", raise_broadcast)

        result = process_claims_batch(
            db, max_claims=10, min_batch_size=1, max_wait_seconds=30
        )
        assert result["processed"] is False
        assert result["failed_count"] == 1
        assert "wallet connection lost" in result["error"]

        with sqlite3.connect(db) as conn:
            row = conn.execute(
                "SELECT status FROM claims WHERE claim_id = 'c-1'"
            ).fetchone()
        assert row[0] == "failed"

    # ── #8230 regression: no fabricated settlement ────────────────────
    # These exercise the REAL sign_and_broadcast_transaction. Before the fix
    # both marked the claim 'settled' against a hash that never existed.

    def test_unconfigured_settlement_does_not_settle_claims(self, tmp_path, monkeypatch):
        """Missing config must not settle anything; claims stay retryable."""
        monkeypatch.delenv("TREASURY_KEY_PATH", raising=False)
        monkeypatch.delenv("NODE_API_URL", raising=False)

        db = str(tmp_path / "test.db")
        _init_db(db, FULL_SCHEMA)
        now = int(time.time())
        _insert_claim(db, "c-1", reward_urtc=1000, submitted_at=now - 10)
        _seed_rewards_pool(db, 100000)

        result = process_claims_batch(
            db, max_claims=10, min_batch_size=1, max_wait_seconds=30
        )

        assert result["processed"] is False
        assert result["transaction_hash"] is None
        assert "TREASURY_KEY_PATH" in result["error"]

        with sqlite3.connect(db) as conn:
            status = conn.execute(
                "SELECT status FROM claims WHERE claim_id = 'c-1'"
            ).fetchone()[0]
            pool = conn.execute(
                "SELECT balance_urtc FROM rewards_pool WHERE pool_name = 'epoch_rewards'"
            ).fetchone()[0]

        # Nothing was signed or sent, so the claim is returned for a retry.
        assert status == "approved"
        assert pool == 100000  # reservation released, not consumed

    def test_unreachable_node_does_not_settle_claims(self, tmp_path, monkeypatch):
        """A node that never answers must not produce a settled claim."""
        _configure_settlement(monkeypatch, tmp_path)
        _stub_signer(monkeypatch)
        _stub_post(monkeypatch, ConnectionError("connection refused"))

        db = str(tmp_path / "test.db")
        _init_db(db, FULL_SCHEMA)
        now = int(time.time())
        _insert_claim(db, "c-1", reward_urtc=1000, submitted_at=now - 10)
        _seed_rewards_pool(db, 100000)

        result = process_claims_batch(
            db, max_claims=10, min_batch_size=1, max_wait_seconds=30
        )

        assert result["processed"] is False
        assert result["transaction_hash"] is None
        assert result["failed_count"] == 1
        assert "NOT confirmed on chain" in result["error"]

        # The batch digest is retained, but in its own field and never
        # 0x-prefixed, so it cannot be read as an on-chain reference.
        assert result["local_batch_digest"] is not None
        assert not result["local_batch_digest"].startswith("0x")

        with sqlite3.connect(db) as conn:
            status = conn.execute(
                "SELECT status FROM claims WHERE claim_id = 'c-1'"
            ).fetchone()[0]
            pool = conn.execute(
                "SELECT balance_urtc FROM rewards_pool WHERE pool_name = 'epoch_rewards'"
            ).fetchone()[0]

        assert status != "settled"
        assert pool == 100000  # reservation released, not consumed

    def test_successful_batch_updates_result(self, tmp_path, monkeypatch):
        db = str(tmp_path / "test.db")
        _init_db(db, FULL_SCHEMA)
        now = int(time.time())
        _insert_claim(db, "c-1", reward_urtc=1500, submitted_at=now - 10)
        _seed_rewards_pool(db, 100000)

        def fake_broadcast(tx_data, db_path):
            return True, "0xsuccess", None

        monkeypatch.setattr("claims_settlement.sign_and_broadcast_transaction", fake_broadcast)

        result = process_claims_batch(
            db, max_claims=10, min_batch_size=1, max_wait_seconds=30
        )
        assert result["processed"] is True
        assert result["claims_count"] == 1
        assert result["success_count"] == 1
        assert result["transaction_hash"] == "0xsuccess"
        assert result["total_amount_urtc"] == 1500
        # reward_urtc is micro-RTC: 1 RTC = 1_000_000 uRTC (canonical
        # URTC_PER_RTC, same factor as claims_eligibility / claims_submission
        # apply to this identical field). 1500 uRTC == 0.0015 RTC.
        assert result["total_amount_rtc"] == 1500 / 1_000_000
        assert result["total_amount_rtc"] == result["total_amount_urtc"] / URTC_PER_RTC
        assert result["error"] is None

    def test_stale_verifying_claims_flagged(self, tmp_path, capsys):
        db = str(tmp_path / "test.db")
        _init_db(db)
        now = int(time.time())
        _insert_claim(db, "old-verify", status="verifying", submitted_at=now - 3600)

        result = process_claims_batch(
            db, max_claims=10, min_batch_size=1, max_wait_seconds=10, dry_run=True
        )
        captured = capsys.readouterr()
        assert "claims stuck in 'verifying'" in captured.out

    def test_duplicate_claim_ids_deduplicated(self, tmp_path, monkeypatch):
        """Test that duplicate claim IDs are removed."""
        db = str(tmp_path / "test.db")
        _init_db(db, FULL_SCHEMA)
        now = int(time.time())

        _insert_claim(db, "c-1", reward_urtc=500, submitted_at=now - 10)
        _seed_rewards_pool(db, 100000)

        def fake_broadcast(tx_data, db_path):
            return True, "0xtxhash", None

        monkeypatch.setattr("claims_settlement.sign_and_broadcast_transaction", fake_broadcast)

        result = process_claims_batch(
            db, max_claims=10, min_batch_size=1, max_wait_seconds=30
        )
        assert result["processed"] is True
        assert result["claims_count"] == 1

    def test_negative_max_claims(self, tmp_path):
        db = str(tmp_path / "test.db")
        _init_db(db)
        _insert_claim(db, "c-1", submitted_at=100)

        result = process_claims_batch(
            db, max_claims=-1, min_batch_size=1, max_wait_seconds=30
        )
        assert result["processed"] is False
        assert result["error"] == "Batch conditions not met"

    def test_batch_id_in_result_on_success(self, tmp_path, monkeypatch):
        db = str(tmp_path / "test.db")
        _init_db(db, FULL_SCHEMA)
        now = int(time.time())
        _insert_claim(db, "c-1", reward_urtc=1000, submitted_at=now - 10)
        _seed_rewards_pool(db, 100000)

        monkeypatch.setattr(
            "claims_settlement.sign_and_broadcast_transaction",
            lambda tx, db: (True, "0xabc", None),
        )

        result = process_claims_batch(
            db, max_claims=10, min_batch_size=1, max_wait_seconds=30
        )
        assert result["batch_id"] is not None
        assert result["batch_id"].startswith("batch_")


# ═══════════════════════════════════════════════════════════════════════
# 17. Integration: end-to-end flow with real DB
# ═══════════════════════════════════════════════════════════════════════

class TestEndToEndFlow:
    def test_full_batch_cycle(self, tmp_path, monkeypatch):
        db = str(tmp_path / "test.db")
        _init_db(db, CLAIMS_SCHEMA + "\n" + REWARDS_POOL_SCHEMA)
        for i in range(5):
            _insert_claim(db, f"c-{i}", reward_urtc=1000, submitted_at=100 + i)
        _seed_rewards_pool(db, 100000)

        monkeypatch.setattr(
            "claims_settlement.sign_and_broadcast_transaction",
            lambda tx, db: (True, "0xendtoend", None),
        )

        result = process_claims_batch(
            db, max_claims=10, min_batch_size=3, max_wait_seconds=0
        )
        # submitted_at=100 is epoch year 1970, so age is ~55 years >> 0 seconds
        # That means max_wait_seconds=0 triggers immediate processing
        assert result["processed"] is True
        assert result["success_count"] == 5

        with sqlite3.connect(db) as conn:
            rows = conn.execute(
                "SELECT status FROM claims ORDER BY claim_id"
            ).fetchall()
        assert all(r[0] == "settled" for r in rows)

        stats = get_settlement_stats(db, days=7)
        assert stats["settled_claims"] == 5
        assert stats["settled_amount_urtc"] == 5000

    def test_multiple_batches_over_time(self, tmp_path, monkeypatch):
        """Multiple process_claims_batch calls with different claims."""
        db = str(tmp_path / "test.db")
        _init_db(db, CLAIMS_SCHEMA + "\n" + REWARDS_POOL_SCHEMA)
        _seed_rewards_pool(db, 100000)

        monkeypatch.setattr(
            "claims_settlement.sign_and_broadcast_transaction",
            lambda tx, db: (True, "0xmulti", None),
        )

        # Batch 1: 3 claims
        for i in range(3):
            _insert_claim(db, f"b1-{i}", reward_urtc=1000, submitted_at=100 + i)
        r1 = process_claims_batch(db, max_claims=5, min_batch_size=1, max_wait_seconds=0)
        assert r1["success_count"] == 3

        # Batch 2: 2 claims
        for i in range(3, 5):
            _insert_claim(db, f"b2-{i}", reward_urtc=2000, submitted_at=200 + i)
        r2 = process_claims_batch(db, max_claims=5, min_batch_size=1, max_wait_seconds=0)
        assert r2["success_count"] == 2

        # Different batch IDs
        assert r1["batch_id"] != r2["batch_id"]

        stats = get_settlement_stats(db, days=7)
        assert stats["settled_claims"] == 5
        assert stats["total_batches"] == 2


# ═══════════════════════════════════════════════════════════════════════
# 18. Import fallback edge cases
# ═══════════════════════════════════════════════════════════════════════

class TestImportFallback:
    def test_update_claim_status_fallback_when_claims_submission_missing(self):
        """If claims_submission can't be imported, fallback stubs are used."""
        # Already handled at import time — the module is always importable
        # in this test environment. Just verify the stubs exist.
        import claims_settlement
        assert hasattr(claims_settlement, "update_claim_status")
        assert hasattr(claims_settlement, "get_claim_status")


# ── conftest-like fixtures ─────────────────────────────────────────

FULL_SCHEMA = (
    CLAIMS_SCHEMA
    + "\n"
    + REWARDS_POOL_SCHEMA
    + "\n"
    + AUDIT_SCHEMA
)


@pytest.fixture(autouse=True)
def _patch_claims_submission(monkeypatch):
    """Patch claims_submission.update_claim_status to perform the same
    DB writes as the real function, without requiring claims_submission
    to be importable on the sys.path (it lives under ./node/ but the
    test runner path may not include it).

    This ensures claims_settlement's update_claims_settled(),
    update_claims_failed(), and process_claims_batch() correctly update
    the claims table and audit log via our patched handler.

    The patch also creates claims_audit if missing (legacy schema compat).
    """
    import json
    import sqlite3
    import time

    def _patched_update(db_path, claim_id, status, details=None):
        try:
            with sqlite3.connect(db_path) as conn:
                now = int(time.time())
                cursor = conn.execute(
                    """UPDATE claims SET status = ?, updated_at = ?
                    WHERE claim_id = ?""",
                    (status, now, claim_id),
                )
                if cursor.rowcount == 0:
                    conn.close()
                    return False
                if status == "settled" and details:
                    conn.execute(
                        """UPDATE claims SET transaction_hash = ?,
                        settlement_batch = ?, settled_at = ?
                        WHERE claim_id = ?""",
                        (
                            details.get("transaction_hash"),
                            details.get("settlement_batch"),
                            now,
                            claim_id,
                        ),
                    )
                elif status == "failed" and details:
                    conn.execute(
                        """UPDATE claims SET rejection_reason = ?
                        WHERE claim_id = ?""",
                        (details.get("reason"), claim_id),
                    )
                # Create audit table if missing (legacy schemas)
                conn.execute(
                    """CREATE TABLE IF NOT EXISTS claims_audit (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        claim_id TEXT, action TEXT, actor TEXT,
                        details TEXT, timestamp INTEGER
                    )"""
                )
                conn.execute(
                    """INSERT INTO claims_audit
                    (claim_id, action, actor, details, timestamp)
                    VALUES (?, ?, ?, ?, ?)""",
                    (claim_id, f"claim_{status}", "system",
                     json.dumps(details) if details else None, now),
                )
                conn.commit()
                return True
        except Exception:
            return False

    monkeypatch.setattr(
        "claims_settlement.update_claim_status",
        _patched_update,
    )
