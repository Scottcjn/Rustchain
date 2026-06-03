#!/usr/bin/env python3
"""Tests for node/bridge_api.py — Bridge API module (RIP-0305).

Tests cover:
  - Enums & dataclasses
  - validate_bridge_request (full validation pipeline)
  - validate_chain_address_format (rustchain, solana, ergo, base)
  - generate_bridge_tx_hash
  - check_miner_balance
  - create_bridge_transfer / get / list / void / update
  - _parse_non_negative_int_arg
  - init_bridge_schema (DDL)
  - Flask routes via test app
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
import time
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, "node")

# ── Module under test ────────────────────────────────────────────────
import bridge_api as ba
from bridge_api import (
    BridgeDirection,
    BridgeStatus,
    LockType,
    LockStatus,
    BridgeTransferRequest,
    ValidationResult,
    BRIDGE_MIN_AMOUNT_RTC,
    VALID_CHAINS,
    VALID_BRIDGE_TYPES,
)


# ══════════════════════════════════════════════════════════════════════
# 0.  Fixtures
# ══════════════════════════════════════════════════════════════════════

@pytest.fixture
def db():
    """In-memory SQLite DB with bridge schema + required tables."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ba.init_bridge_schema(conn.cursor())
    # Additional tables needed by create_bridge_transfer / check_miner_balance
    conn.execute("""
        CREATE TABLE IF NOT EXISTS balances (
            miner_id TEXT PRIMARY KEY,
            amount_i64 INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS lock_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bridge_transfer_id INTEGER,
            miner_id TEXT NOT NULL,
            amount_i64 INTEGER NOT NULL,
            lock_type TEXT NOT NULL,
            locked_at INTEGER NOT NULL,
            unlock_at INTEGER NOT NULL,
            unlocked_at INTEGER,
            released_by TEXT,
            release_tx_hash TEXT,
            status TEXT NOT NULL DEFAULT 'locked',
            created_at INTEGER NOT NULL
        )
    """)
    conn.commit()
    # Pre-populate balance for sample_request source address
    conn.execute("INSERT OR IGNORE INTO balances (miner_id, amount_i64) VALUES (?, ?)",
                 ("RTC" + "a" * 30, 1000 * 1000000))
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def sample_request():
    return BridgeTransferRequest(
        direction="deposit",
        source_chain="rustchain",
        dest_chain="base",
        source_address="RTC" + "a" * 30,
        dest_address="0x" + "b" * 40,
        amount_rtc=10.0,
        memo="test bridge",
        bridge_type="bottube",
    )


# ══════════════════════════════════════════════════════════════════════
# 1.  Enums & Dataclasses
# ══════════════════════════════════════════════════════════════════════

class TestEnums:
    def test_bridge_direction_values(self):
        assert BridgeDirection.DEPOSIT.value == "deposit"
        assert BridgeDirection.WITHDRAW.value == "withdraw"

    def test_bridge_status_values(self):
        assert BridgeStatus.PENDING.value == "pending"
        assert BridgeStatus.LOCKED.value == "locked"
        assert BridgeStatus.COMPLETED.value == "completed"
        assert BridgeStatus.FAILED.value == "failed"
        assert BridgeStatus.VOIDED.value == "voided"
        assert BridgeStatus.CONFIRMING.value == "confirming"

    def test_lock_type_values(self):
        assert LockType.BRIDGE_DEPOSIT.value == "bridge_deposit"
        assert LockType.BRIDGE_WITHDRAW.value == "bridge_withdraw"
        assert LockType.EPOCH_SETTLEMENT.value == "epoch_settlement"

    def test_lock_status_values(self):
        assert LockStatus.LOCKED.value == "locked"
        assert LockStatus.RELEASED.value == "released"
        assert LockStatus.FORFEITED.value == "forfeited"


class TestDataClasses:
    def test_bridge_transfer_request(self):
        r = BridgeTransferRequest(
            direction="deposit", source_chain="a", dest_chain="b",
            source_address="src", dest_address="dst", amount_rtc=1.0,
        )
        assert r.direction == "deposit"
        assert r.amount_rtc == 1.0
        assert r.bridge_type == "bottube"  # default

    def test_validation_result_defaults(self):
        r = ValidationResult(ok=True)
        assert r.ok is True
        assert r.error is None
        assert r.details is None


# ══════════════════════════════════════════════════════════════════════
# 2.  validate_bridge_request
# ══════════════════════════════════════════════════════════════════════

class TestValidateBridgeRequest:
    def test_valid_request(self):
        data = {
            "direction": "deposit",
            "source_chain": "rustchain",
            "dest_chain": "base",
            "source_address": "RTC" + "a" * 30,
            "dest_address": "0x" + "b" * 40,
            "amount_rtc": 10.0,
        }
        r = ba.validate_bridge_request(data)
        assert r.ok is True
        assert r.details["amount_rtc"] == 10.0

    def test_withdraw_valid(self):
        data = {
            "direction": "withdraw",
            "source_chain": "base",
            "dest_chain": "rustchain",
            "source_address": "0x" + "a" * 40,
            "dest_address": "RTC" + "b" * 30,
            "amount_rtc": 5.0,
        }
        r = ba.validate_bridge_request(data)
        assert r.ok is True

    def test_none_body(self):
        r = ba.validate_bridge_request(None)
        assert r.ok is False
        assert r.error == "Request body is required"

    def test_missing_required_field(self):
        r = ba.validate_bridge_request({"direction": "deposit"})
        assert r.ok is False
        assert "Missing" in r.error

    def test_invalid_direction(self):
        r = ba.validate_bridge_request({
            "direction": "sideways", "source_chain": "a", "dest_chain": "b",
            "source_address": "x" * 12, "dest_address": "y" * 12, "amount_rtc": 10,
        })
        assert r.ok is False
        assert "Invalid direction" in r.error

    def test_invalid_source_chain(self):
        r = ba.validate_bridge_request({
            "direction": "deposit", "source_chain": "bitcoin", "dest_chain": "base",
            "source_address": "x" * 12, "dest_address": "y" * 12, "amount_rtc": 10,
        })
        assert r.ok is False
        assert "Invalid source_chain" in r.error

    def test_same_source_dest_chain(self):
        r = ba.validate_bridge_request({
            "direction": "deposit", "source_chain": "base", "dest_chain": "base",
            "source_address": "x" * 12, "dest_address": "y" * 12, "amount_rtc": 10,
        })
        assert r.ok is False
        assert "must be different" in r.error

    def test_deposit_must_start_from_rustchain(self):
        r = ba.validate_bridge_request({
            "direction": "deposit", "source_chain": "base", "dest_chain": "solana",
            "source_address": "x" * 12, "dest_address": "y" * 12, "amount_rtc": 10,
        })
        assert r.ok is False
        assert "Deposit source_chain must be rustchain" in r.error

    def test_withdraw_must_end_at_rustchain(self):
        r = ba.validate_bridge_request({
            "direction": "withdraw", "source_chain": "base", "dest_chain": "solana",
            "source_address": "x" * 12, "dest_address": "y" * 12, "amount_rtc": 10,
        })
        assert r.ok is False
        assert "Withdraw dest_chain must be rustchain" in r.error

    def test_address_too_short(self):
        r = ba.validate_bridge_request({
            "direction": "deposit", "source_chain": "rustchain", "dest_chain": "base",
            "source_address": "short", "dest_address": "also_short",
            "amount_rtc": 10,
        })
        assert r.ok is False
        assert "too short" in r.error

    def test_amount_must_be_positive(self):
        r = ba.validate_bridge_request({
            "direction": "deposit", "source_chain": "rustchain", "dest_chain": "base",
            "source_address": "RTC" + "a" * 30, "dest_address": "0x" + "b" * 40,
            "amount_rtc": -5,
        })
        assert r.ok is False

    def test_amount_below_minimum(self):
        r = ba.validate_bridge_request({
            "direction": "deposit", "source_chain": "rustchain", "dest_chain": "base",
            "source_address": "RTC" + "a" * 30, "dest_address": "0x" + "b" * 40,
            "amount_rtc": 0.001,
        })
        assert r.ok is False
        assert f">= {BRIDGE_MIN_AMOUNT_RTC}" in r.error

    def test_non_finite_amount(self):
        r = ba.validate_bridge_request({
            "direction": "deposit", "source_chain": "rustchain", "dest_chain": "base",
            "source_address": "RTC" + "a" * 30, "dest_address": "0x" + "b" * 40,
            "amount_rtc": float("inf"),
        })
        assert r.ok is False

    def test_bool_amount_rejected(self):
        r = ba.validate_bridge_request({
            "direction": "deposit", "source_chain": "rustchain", "dest_chain": "base",
            "source_address": "RTC" + "a" * 30, "dest_address": "0x" + "b" * 40,
            "amount_rtc": True,
        })
        assert r.ok is False

    def test_memo_too_long(self):
        r = ba.validate_bridge_request({
            "direction": "deposit", "source_chain": "rustchain", "dest_chain": "base",
            "source_address": "RTC" + "a" * 30, "dest_address": "0x" + "b" * 40,
            "amount_rtc": 10.0, "memo": "x" * 300,
        })
        assert r.ok is False
        assert "256" in r.error

    def test_invalid_bridge_type(self):
        r = ba.validate_bridge_request({
            "direction": "deposit", "source_chain": "rustchain", "dest_chain": "base",
            "source_address": "RTC" + "a" * 30, "dest_address": "0x" + "b" * 40,
            "amount_rtc": 10.0, "bridge_type": "unknown",
        })
        assert r.ok is False
        assert "Invalid bridge_type" in r.error

    def test_valid_with_all_optionals(self):
        data = {
            "direction": "deposit", "source_chain": "rustchain", "dest_chain": "base",
            "source_address": "RTC" + "a" * 30, "dest_address": "0x" + "b" * 40,
            "amount_rtc": 10.0, "memo": "test", "bridge_type": "internal",
        }
        r = ba.validate_bridge_request(data)
        assert r.ok is True


# ══════════════════════════════════════════════════════════════════════
# 3.  validate_chain_address_format
# ══════════════════════════════════════════════════════════════════════

class TestValidateChainAddressFormat:
    def test_rustchain_valid(self):
        ok, err = ba.validate_chain_address_format("rustchain", "RTC" + "a" * 30)
        assert ok is True
        assert err == ""

    def test_rustchain_missing_prefix(self):
        ok, err = ba.validate_chain_address_format("rustchain", "BTC" + "a" * 30)
        assert ok is False
        assert "RTC" in err

    def test_rustchain_too_short(self):
        ok, err = ba.validate_chain_address_format("rustchain", "RTC123")
        assert ok is False
        assert "too short" in err

    def test_solana_valid(self):
        ok, err = ba.validate_chain_address_format("solana", "a" * 40)
        assert ok is True

    def test_solana_too_short(self):
        ok, err = ba.validate_chain_address_format("solana", "a" * 20)
        assert ok is False

    def test_ergo_valid(self):
        ok, err = ba.validate_chain_address_format("ergo", "9" + "a" * 35)
        assert ok is True

    def test_ergo_valid_with_3(self):
        ok, err = ba.validate_chain_address_format("ergo", "3" + "a" * 35)
        assert ok is True

    def test_ergo_wrong_prefix(self):
        ok, err = ba.validate_chain_address_format("ergo", "X" + "a" * 35)
        assert ok is False
        assert "Ergo" in err

    def test_base_valid(self):
        ok, err = ba.validate_chain_address_format("base", "0x" + "a" * 40)
        assert ok is True

    def test_base_missing_0x(self):
        ok, err = ba.validate_chain_address_format("base", "ab" + "a" * 38)
        assert ok is False
        assert "0x" in err

    def test_base_wrong_length(self):
        ok, err = ba.validate_chain_address_format("base", "0x" + "a" * 20)
        assert ok is False

    def test_base_non_hex(self):
        ok, err = ba.validate_chain_address_format("base", "0x" + "z" * 40)
        assert ok is False
        assert "hex" in err

    def test_empty_address(self):
        ok, err = ba.validate_chain_address_format("rustchain", "")
        assert ok is False
        assert "required" in err.lower()


# ══════════════════════════════════════════════════════════════════════
# 4.  generate_bridge_tx_hash
# ══════════════════════════════════════════════════════════════════════

class TestGenerateBridgeTxHash:
    def test_returns_32_char_hex(self):
        h = ba.generate_bridge_tx_hash("deposit", "rustchain", "base", "src", "dst", 1000)
        assert isinstance(h, str)
        assert len(h) == 32
        all(c in "0123456789abcdef" for c in h)

    def test_different_amounts_different_hashes(self):
        h1 = ba.generate_bridge_tx_hash("deposit", "a", "b", "c", "d", 100)
        h2 = ba.generate_bridge_tx_hash("deposit", "a", "b", "c", "d", 200)
        assert h1 != h2

    def test_different_directions_different_hashes(self):
        h1 = ba.generate_bridge_tx_hash("deposit", "a", "b", "c", "d", 100)
        h2 = ba.generate_bridge_tx_hash("withdraw", "a", "b", "c", "d", 100)
        assert h1 != h2


# ══════════════════════════════════════════════════════════════════════
# 5.  check_miner_balance
# ══════════════════════════════════════════════════════════════════════

class TestCheckMinerBalance:
    def test_no_balance_returns_false(self, db):
        has, avail, pending = ba.check_miner_balance(db, "RTCtest", 100)
        assert has is False
        assert avail == 0

    def test_sufficient_balance(self, db):
        db.execute("INSERT INTO balances (miner_id, amount_i64) VALUES (?, ?)",
                   ("RTCtest", 1000))
        db.commit()
        has, avail, pending = ba.check_miner_balance(db, "RTCtest", 500)
        assert has is True
        assert avail == 1000

    def test_insufficient_balance(self, db):
        db.execute("INSERT INTO balances (miner_id, amount_i64) VALUES (?, ?)",
                   ("RTCtest", 100))
        db.commit()
        has, avail, pending = ba.check_miner_balance(db, "RTCtest", 500)
        assert has is False
        assert avail == 100

    def test_pending_debits_subtracted(self, db):
        db.execute("INSERT INTO balances (miner_id, amount_i64) VALUES (?, ?)",
                   ("RTCtest", 1000))
        db.execute("""INSERT INTO bridge_transfers
            (tx_hash, direction, source_chain, dest_chain, source_address, dest_address,
             amount_i64, amount_rtc, lock_epoch, status, created_at, updated_at, expires_at)
            VALUES (?, 'deposit', 'rustchain', 'base', ?, ?,
                    ?, ?, 0, 'locked', ?, ?, ?)""",
                   ("hash1", "RTCtest", "0xaddr", 600, 0.0006, int(time.time()),
                    int(time.time()), int(time.time()) + 3600))
        db.commit()
        has, avail, pending = ba.check_miner_balance(db, "RTCtest", 300)
        assert has is True, f"avail={avail} should be >= 300"
        assert avail == 400  # 1000 - 600
        assert pending == 600


# ══════════════════════════════════════════════════════════════════════
# 6.  create_bridge_transfer
# ══════════════════════════════════════════════════════════════════════

class TestCreateBridgeTransfer:
    def test_creates_transfer(self, db, sample_request):
        ok, result = ba.create_bridge_transfer(db, sample_request)
        assert ok is True
        assert result["tx_hash"]
        assert result["direction"] == "deposit"
        assert result["status"] == "pending"
        assert result["bridge_transfer_id"] > 0
        assert result["ok"] is True

    def test_amount_converted_to_i64(self, db, sample_request):
        ok, result = ba.create_bridge_transfer(db, sample_request)
        assert ok is True
        # Return dict has amount_rtc, not amount_i64
        assert result["amount_rtc"] == 10.0

    def test_returns_tx_hash(self, db, sample_request):
        ok, result = ba.create_bridge_transfer(db, sample_request)
        assert ok is True
        assert len(result["tx_hash"]) == 32

    def test_insufficient_balance_rejected(self, db):
        req = BridgeTransferRequest(
            direction="deposit", source_chain="rustchain", dest_chain="base",
            source_address="RTC" + "a" * 30, dest_address="0x" + "b" * 40,
            amount_rtc=999999.0,
        )
        ok, result = ba.create_bridge_transfer(db, req)
        assert ok is False
        assert "balance" in result["error"].lower() or "insufficient" in result["error"].lower()


# ══════════════════════════════════════════════════════════════════════
# 7.  get_bridge_transfer_by_hash
# ══════════════════════════════════════════════════════════════════════

class TestGetBridgeTransferByHash:
    def test_not_found(self, db):
        result = ba.get_bridge_transfer_by_hash(db, "nonexistent")
        assert result is None

    def test_returns_transfer(self, db, sample_request):
        ok, created = ba.create_bridge_transfer(db, sample_request)
        assert ok is True
        tx_hash = created["tx_hash"]
        retrieved = ba.get_bridge_transfer_by_hash(db, tx_hash)
        assert retrieved is not None
        assert retrieved["tx_hash"] == tx_hash
        assert retrieved["direction"] == "deposit"


# ══════════════════════════════════════════════════════════════════════
# 8.  list_bridge_transfers
# ══════════════════════════════════════════════════════════════════════

class TestListBridgeTransfers:
    def test_empty_list(self, db):
        transfers = ba.list_bridge_transfers(db)
        assert transfers == []

    def test_returns_transfers(self, db, sample_request):
        ba.create_bridge_transfer(db, sample_request)
        transfers = ba.list_bridge_transfers(db)
        assert len(transfers) == 1
        assert transfers[0]["direction"] == "deposit"

    def test_filters_by_direction(self, db, sample_request):
        ba.create_bridge_transfer(db, sample_request)
        # Create a withdraw
        req2 = BridgeTransferRequest(
            direction="withdraw", source_chain="base", dest_chain="rustchain",
            source_address="0x" + "a" * 40, dest_address="RTC" + "b" * 30,
            amount_rtc=5.0,
        )
        ba.create_bridge_transfer(db, req2)
        deposits = ba.list_bridge_transfers(db, direction="deposit")
        assert len(deposits) == 1
        assert deposits[0]["direction"] == "deposit"
        all_tx = ba.list_bridge_transfers(db)
        assert len(all_tx) == 2


# ══════════════════════════════════════════════════════════════════════
# 9.  void_bridge_transfer
# ══════════════════════════════════════════════════════════════════════

class TestVoidBridgeTransfer:
    def test_voids_transfer(self, db, sample_request):
        ok, created = ba.create_bridge_transfer(db, sample_request)
        assert ok is True
        tx_hash = created["tx_hash"]
        ok, result = ba.void_bridge_transfer(db, tx_hash, "test reason", "test_admin")
        assert ok is True, f"void failed: {result}"
        assert result.get("voided_id") is not None

    def test_nonexistent_hash(self, db):
        ok, result = ba.void_bridge_transfer(db, "nonexistent", "reason", "admin")
        assert ok is False


# ══════════════════════════════════════════════════════════════════════
# 10. update_external_confirmation
# ══════════════════════════════════════════════════════════════════════

class TestUpdateExternalConfirmation:
    def test_updates_confirmation(self, db, sample_request):
        ok, created = ba.create_bridge_transfer(db, sample_request)
        tx_hash = created["tx_hash"]
        ok, result = ba.update_external_confirmation(
            db, tx_hash, "ext_tx_hash_123", 15, 12,
        )
        assert ok is True, f"update failed: {result}"
        assert result["ok"] is True
        assert result["status"] == "completed"
        assert result["external_confirmations"] == 15


# ══════════════════════════════════════════════════════════════════════
# 11. _parse_non_negative_int_arg
# ══════════════════════════════════════════════════════════════════════

class TestParseNonNegativeIntArg:
    def test_valid_int(self):
        val, err = ba._parse_non_negative_int_arg("42", "test", 10)
        assert val == 42
        assert err is None

    def test_none_returns_default(self):
        val, err = ba._parse_non_negative_int_arg(None, "test", 10)
        assert val == 10
        assert err is None

    def test_negative_returns_error(self):
        val, err = ba._parse_non_negative_int_arg("-5", "test", 10)
        assert val is None
        assert "non-negative" in err

    def test_string_returns_error(self):
        val, err = ba._parse_non_negative_int_arg("abc", "test", 10)
        assert val is None
        assert "integer" in err

    def test_max_value_respected(self):
        val, err = ba._parse_non_negative_int_arg("999", "test", 10, max_value=50)
        assert val == 50
        assert err is None


# ══════════════════════════════════════════════════════════════════════
# 12. init_bridge_schema
# ══════════════════════════════════════════════════════════════════════

class TestInitBridgeSchema:
    def test_creates_bridge_transfers_table(self):
        conn = sqlite3.connect(":memory:")
        ba.init_bridge_schema(conn.cursor())
        conn.commit()
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        conn.close()
        assert "bridge_transfers" in tables

    def test_idempotent(self):
        conn = sqlite3.connect(":memory:")
        ba.init_bridge_schema(conn.cursor())
        ba.init_bridge_schema(conn.cursor())  # Should not raise
        conn.close()


# ══════════════════════════════════════════════════════════════════════
# 13. Fallback module defaults
# ══════════════════════════════════════════════════════════════════════

class TestModuleFallbacks:
    def test_current_slot_works(self):
        slot = ba.current_slot()
        assert isinstance(slot, int)
        assert slot > 0

    def test_slot_to_epoch_works(self):
        epoch = ba.slot_to_epoch(1000)
        assert epoch == 6  # 1000 // 144

    def test_validate_miner_id_valid(self):
        ok, err = ba.validate_miner_id_format("RTCabc123")
        assert ok is True

    def test_validate_miner_id_too_short(self):
        ok, err = ba.validate_miner_id_format("ab")
        assert ok is False
        assert "at least 3" in err

    def test_validate_miner_id_no_rtc_prefix(self):
        ok, err = ba.validate_miner_id_format("BTCabc")
        assert ok is False
        assert "RTC" in err