#!/usr/bin/env python3
"""
Tests for RIP-0305: Bridge API + Lock Ledger
============================================

Test coverage:
- Bridge transfer initiation (deposit/withdraw)
- Bridge status queries
- Bridge list with filters
- Bridge void operations
- External confirmation updates
- Lock ledger creation/release
- Lock queries by miner
- Auto-release of expired locks
"""

import pytest
import sqlite3
import time
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
from dataclasses import dataclass
from typing import Optional, Tuple, Dict, Any, List
from flask import Flask

# Add node directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "node"))


# =============================================================================
# Inline module imports for testing (to allow DB_PATH patching)
# =============================================================================

def get_bridge_api(db_path: str):
    """Import bridge_api with custom DB_PATH."""
    import importlib.util
    import types
    
    # Read the source code
    source_path = str(Path(__file__).parent.parent / "node" / "bridge_api.py")
    with open(source_path, 'r', encoding='utf-8') as f:
        source = f.read()
    
    # Create module
    module = types.ModuleType("bridge_api")
    module.DB_PATH = db_path
    
    # Execute with DB_PATH already set
    exec(compile(source, source_path, 'exec'), module.__dict__)  # nosec B102
    return module


def get_lock_ledger(db_path: str):
    """Import lock_ledger with custom DB_PATH."""
    import importlib.util
    import types
    
    # Read the source code
    source_path = str(Path(__file__).parent.parent / "node" / "lock_ledger.py")
    with open(source_path, 'r', encoding='utf-8') as f:
        source = f.read()
    
    # Create module
    module = types.ModuleType("lock_ledger")
    module.DB_PATH = db_path
    
    # Execute with DB_PATH already set
    exec(compile(source, source_path, 'exec'), module.__dict__)  # nosec B102
    return module


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def setup_test_db(tmp_path):
    """Create a test database with required schema and return configured modules."""
    db_path = str(tmp_path / "test_rustchain.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create balances table (needed for balance checks)
    cursor.execute("""
        CREATE TABLE balances (
            miner_id TEXT PRIMARY KEY,
            amount_i64 INTEGER DEFAULT 0
        )
    """)
    
    # Create bridge_transfers table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bridge_transfers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            direction TEXT NOT NULL CHECK (direction IN ('deposit', 'withdraw')),
            source_chain TEXT NOT NULL,
            dest_chain TEXT NOT NULL,
            source_address TEXT NOT NULL,
            dest_address TEXT NOT NULL,
            amount_i64 INTEGER NOT NULL CHECK (amount_i64 > 0),
            amount_rtc REAL NOT NULL,
            bridge_type TEXT NOT NULL DEFAULT 'bottube',
            bridge_fee_i64 INTEGER DEFAULT 0,
            external_tx_hash TEXT,
            external_confirmations INTEGER DEFAULT 0,
            required_confirmations INTEGER DEFAULT 12,
            status TEXT NOT NULL DEFAULT 'pending' 
                CHECK (status IN ('pending', 'locked', 'confirming', 'completed', 'failed', 'voided')),
            lock_epoch INTEGER NOT NULL,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL,
            expires_at INTEGER,
            completed_at INTEGER,
            tx_hash TEXT UNIQUE NOT NULL,
            voided_by TEXT,
            voided_reason TEXT,
            failure_reason TEXT,
            memo TEXT,
            source_debited INTEGER NOT NULL DEFAULT 0
        )
    """)

    # Create lock_ledger table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lock_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bridge_transfer_id INTEGER,
            miner_id TEXT NOT NULL,
            amount_i64 INTEGER NOT NULL CHECK (amount_i64 > 0),
            lock_type TEXT NOT NULL,
            locked_at INTEGER NOT NULL,
            unlock_at INTEGER NOT NULL,
            unlocked_at INTEGER,
            status TEXT NOT NULL DEFAULT 'locked',
            created_at INTEGER NOT NULL,
            released_by TEXT,
            release_tx_hash TEXT
        )
    """)
    
    # Create indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_bridge_status ON bridge_transfers(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_bridge_source ON bridge_transfers(source_address)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_lock_miner ON lock_ledger(miner_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_lock_status ON lock_ledger(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_lock_unlock_at ON lock_ledger(unlock_at)")
    
    conn.commit()
    conn.close()
    
    # Load modules with this DB path
    bridge_api = get_bridge_api(db_path)
    lock_ledger = get_lock_ledger(db_path)
    
    return {
        'db_path': db_path,
        'bridge_api': bridge_api,
        'lock_ledger': lock_ledger
    }


@pytest.fixture
def funded_miner(setup_test_db):
    """Create a miner with balance in the test database."""
    conn = sqlite3.connect(setup_test_db['db_path'])
    conn.execute(
        "INSERT INTO balances (miner_id, amount_i64) VALUES (?, ?)",
        ("RTC0123456789abcdef0123456789abcdef01234567", 100 * 1000000)  # 100 RTC
    )
    conn.commit()
    conn.close()
    return "RTC0123456789abcdef0123456789abcdef01234567"


def assert_generic_database_error(result):
    assert result == {"error": "Database error"}
    assert "details" not in result
    assert "no such table" not in str(result).lower()


# =============================================================================
# Bridge API Validation Tests
# =============================================================================

class TestBridgeValidation:
    """Test bridge request validation."""
    
    def test_valid_deposit_request(self, setup_test_db):
        """Test valid deposit request passes validation."""
        bridge_api = setup_test_db['bridge_api']
        data = {
            "direction": "deposit",
            "source_chain": "rustchain",
            "dest_chain": "solana",
            "source_address": "RTC_test123",
            "dest_address": "4TRwNqXqXqXqXqXqXqXqXqXqXqXqXqXqXqXq",
            "amount_rtc": 10.0
        }
        result = bridge_api.validate_bridge_request(data)
        assert result.ok is True
        assert result.details["direction"] == "deposit"
    
    def test_valid_withdraw_request(self, setup_test_db):
        """Test valid withdraw request passes validation."""
        bridge_api = setup_test_db['bridge_api']
        data = {
            "direction": "withdraw",
            "source_chain": "solana",
            "dest_chain": "rustchain",
            "source_address": "4TRwNqXqXqXqXqXqXqXqXqXqXqXqXqXqXqXq",
            "dest_address": "RTC_test123",
            "amount_rtc": 5.0
        }
        result = bridge_api.validate_bridge_request(data)
        assert result.ok is True
    
    def test_missing_required_field(self, setup_test_db):
        """Test missing required field fails validation."""
        bridge_api = setup_test_db['bridge_api']
        data = {
            "direction": "deposit",
            "dest_chain": "solana",
            "source_address": "RTC_test123",
            "dest_address": "4TRwNqXqXqXqXqXqXqXqXqXqXqXqXqXqXqXq",
            "amount_rtc": 10.0
        }
        result = bridge_api.validate_bridge_request(data)
        assert result.ok is False
        assert "Missing required field" in result.error
    
    def test_invalid_direction(self, setup_test_db):
        """Test invalid direction fails validation."""
        bridge_api = setup_test_db['bridge_api']
        data = {
            "direction": "invalid",
            "source_chain": "rustchain",
            "dest_chain": "solana",
            "source_address": "RTC_test123",
            "dest_address": "4TRwNqXqXqXqXqXqXqXqXqXqXqXqXqXqXqXq",
            "amount_rtc": 10.0
        }
        result = bridge_api.validate_bridge_request(data)
        assert result.ok is False
        assert "Invalid direction" in result.error
    
    def test_same_chain_fails(self, setup_test_db):
        """Test same source and dest chain fails validation."""
        bridge_api = setup_test_db['bridge_api']
        data = {
            "direction": "deposit",
            "source_chain": "rustchain",
            "dest_chain": "rustchain",
            "source_address": "RTC_test123",
            "dest_address": "RTC_other123",
            "amount_rtc": 10.0
        }
        result = bridge_api.validate_bridge_request(data)
        assert result.ok is False
        assert "must be different" in result.error

    def test_deposit_must_start_from_rustchain(self, setup_test_db):
        """Deposits must be RustChain-to-external so balance locking applies."""
        bridge_api = setup_test_db['bridge_api']
        data = {
            "direction": "deposit",
            "source_chain": "solana",
            "dest_chain": "rustchain",
            "source_address": "4TRwNqXqXqXqXqXqXqXqXqXqXqXqXqXqXqXq",
            "dest_address": "RTC_test123",
            "amount_rtc": 10.0
        }
        result = bridge_api.validate_bridge_request(data)
        assert result.ok is False
        assert "Deposit source_chain must be rustchain" in result.error

    def test_withdraw_must_end_on_rustchain(self, setup_test_db):
        """Withdrawals must be external-to-RustChain, not disguised deposits."""
        bridge_api = setup_test_db['bridge_api']
        data = {
            "direction": "withdraw",
            "source_chain": "rustchain",
            "dest_chain": "solana",
            "source_address": "RTC_test123",
            "dest_address": "4TRwNqXqXqXqXqXqXqXqXqXqXqXqXqXqXqXq",
            "amount_rtc": 10.0
        }
        result = bridge_api.validate_bridge_request(data)
        assert result.ok is False
        assert "Withdraw source_chain must be external" in result.error
    
    def test_amount_below_minimum(self, setup_test_db):
        """Test amount below minimum fails validation."""
        bridge_api = setup_test_db['bridge_api']
        data = {
            "direction": "deposit",
            "source_chain": "rustchain",
            "dest_chain": "solana",
            "source_address": "RTC_test123",
            "dest_address": "4TRwNqXqXqXqXqXqXqXqXqXqXqXqXqXqXqXq",
            "amount_rtc": 0.5
        }
        result = bridge_api.validate_bridge_request(data)
        assert result.ok is False
        assert "must be >=" in result.error


# =============================================================================
# Address Validation Tests
# =============================================================================

class TestAddressValidation:
    """Test chain-specific address validation."""
    
    def test_valid_rustchain_address(self, setup_test_db):
        """Test valid RustChain address."""
        bridge_api = setup_test_db["bridge_api"]
        valid, msg = bridge_api.validate_chain_address_format("rustchain", "RTC0123456789abcdef0123456789abcdef01234567")
        assert valid is True
    
    def test_invalid_rustchain_address_prefix(self, setup_test_db):
        """Test RustChain address without RTC prefix."""
        bridge_api = setup_test_db["bridge_api"]
        valid, msg = bridge_api.validate_chain_address_format("rustchain", "XYZ_test123")
        assert valid is False
        assert "RTC" in msg
    
    def test_valid_solana_address(self, setup_test_db):
        """Test valid Solana address (32-44 chars)."""
        bridge_api = setup_test_db["bridge_api"]
        valid, msg = bridge_api.validate_chain_address_format("solana", "4TRwNqXqXqXqXqXqXqXqXqXqXqXqXqXqXqXq")
        assert valid is True
    
    def test_invalid_solana_address_short(self, setup_test_db):
        """Test Solana address too short."""
        bridge_api = setup_test_db["bridge_api"]
        valid, msg = bridge_api.validate_chain_address_format("solana", "4TRshort")
        assert valid is False
    
    def test_valid_ergo_address(self, setup_test_db):
        """Test valid Ergo address."""
        bridge_api = setup_test_db["bridge_api"]
        valid, msg = bridge_api.validate_chain_address_format("ergo", "9iHwxLXqXqXqXqXqXqXqXqXqXqXqXqXqXqXq")
        assert valid is True
    
    def test_valid_base_address(self, setup_test_db):
        """Test valid Base (Ethereum) address."""
        bridge_api = setup_test_db["bridge_api"]
        valid, msg = bridge_api.validate_chain_address_format("base", "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb0")
        assert valid is True
    
    def test_invalid_base_address_no_0x(self, setup_test_db):
        """Test Base address without 0x prefix."""
        bridge_api = setup_test_db["bridge_api"]
        valid, msg = bridge_api.validate_chain_address_format("base", "742d35Cc6634C0532925a3b844Bc9e7595f0bEb0")
        assert valid is False

    def test_invalid_base_address_non_hex(self, setup_test_db):
        """Test Base address with non-hex characters."""
        bridge_api = setup_test_db["bridge_api"]
        valid, msg = bridge_api.validate_chain_address_format("base", "0xZZ2d35Cc6634C0532925a3b844Bc9e7595f0bEb0")
        assert valid is False
        assert "hex" in msg.lower()


# =============================================================================
# Bridge Transfer Creation Tests
# =============================================================================

class TestBridgeTransferCreation:
    """Test bridge transfer creation."""
    
    def test_create_deposit_transfer(self, setup_test_db, funded_miner):
        """Test creating a deposit bridge transfer."""
        bridge_api = setup_test_db["bridge_api"]
        lock_ledger = setup_test_db["lock_ledger"]
        conn = sqlite3.connect(setup_test_db["db_path"])
        
        req = bridge_api.BridgeTransferRequest(
            direction="deposit",
            source_chain="rustchain",
            dest_chain="solana",
            source_address=funded_miner,
            dest_address="4TRwNqXqXqXqXqXqXqXqXqXqXqXqXqXqXqXq",
            amount_rtc=10.0
        )
        
        success, result = bridge_api.create_bridge_transfer(conn, req)
        
        assert success is True, f"Expected success, got error: {result}"
        assert result["ok"] is True
        assert "bridge_transfer_id" in result
        assert result["amount_rtc"] == 10.0
        assert result["status"] == "pending"
        
        conn.close()
    
    def test_create_withdraw_transfer(self, setup_test_db):
        """Test creating a withdraw bridge transfer (no balance check)."""
        bridge_api = setup_test_db["bridge_api"]
        conn = sqlite3.connect(setup_test_db["db_path"])
        
        req = bridge_api.BridgeTransferRequest(
            direction="withdraw",
            source_chain="solana",
            dest_chain="rustchain",
            source_address="4TRwNqXqXqXqXqXqXqXqXqXqXqXqXqXqXqXq",
            dest_address="RTC_dest123",
            amount_rtc=5.0
        )
        
        success, result = bridge_api.create_bridge_transfer(conn, req)
        
        assert success is True
        assert result["ok"] is True
        assert result["status"] == "pending"
        
        conn.close()
    
    def test_insufficient_balance(self, setup_test_db, funded_miner):
        """Test deposit with insufficient balance fails."""
        bridge_api = setup_test_db["bridge_api"]
        conn = sqlite3.connect(setup_test_db["db_path"])
        
        req = bridge_api.BridgeTransferRequest(
            direction="deposit",
            source_chain="rustchain",
            dest_chain="solana",
            source_address=funded_miner,
            dest_address="4TRwNqXqXqXqXqXqXqXqXqXqXqXqXqXqXqXq",
            amount_rtc=200.0
        )
        
        success, result = bridge_api.create_bridge_transfer(conn, req)
        
        assert success is False
        assert "Insufficient available balance" in result.get("error", "")
        
        conn.close()
    
    def test_admin_deposit_still_requires_funds(self, setup_test_db):
        """Under debit-on-lock, even admin-initiated deposits must hard-debit a
        funded source — you cannot lock RTC that isn't on the ledger.

        (Behavior change: the legacy reservation model let admin bypass the
        balance check entirely. Debit-on-lock makes that unsafe — bridging out
        funds that don't exist would be minting.)
        """
        bridge_api = setup_test_db["bridge_api"]
        conn = sqlite3.connect(setup_test_db["db_path"])

        req = bridge_api.BridgeTransferRequest(
            direction="deposit",
            source_chain="rustchain",
            dest_chain="solana",
            source_address="RTC_unfunded_miner",
            dest_address="4TRwNqXqXqXqXqXqXqXqXqXqXqXqXqXqXqXq",
            amount_rtc=1000.0
        )

        success, result = bridge_api.create_bridge_transfer(conn, req, admin_initiated=True)

        assert success is False
        assert "Insufficient available balance" in result.get("error", "")

        conn.close()

    def test_database_errors_do_not_leak_details(self, setup_test_db):
        """DB failures should not expose SQLite schema details to callers."""
        bridge_api = setup_test_db["bridge_api"]
        conn = sqlite3.connect(":memory:")

        req = bridge_api.BridgeTransferRequest(
            direction="withdraw",
            source_chain="solana",
            dest_chain="rustchain",
            source_address="4TRwNqXqXqXqXqXqXqXqXqXqXqXqXqXqXqXq",
            dest_address="RTC_dest123",
            amount_rtc=5.0
        )

        success, result = bridge_api.create_bridge_transfer(conn, req)

        assert success is False
        assert_generic_database_error(result)

        conn.close()


class TestBridgeInitiateAuth:
    """Test route-level authorization for bridge initiation."""

    def _client(self, bridge_api, db_path):
        bridge_api.DB_PATH = db_path
        app = Flask(__name__)
        bridge_api.register_bridge_routes(app)
        return app.test_client()

    def _deposit_payload(self, source_address):
        return {
            "direction": "deposit",
            "source_chain": "rustchain",
            "dest_chain": "solana",
            "source_address": source_address,
            "dest_address": "4TRwNqXqXqXqXqXqXqXqXqXqXqXqXqXqXqXq",
            "amount_rtc": 10.0,
        }

    def _bridge_row_counts(self, db_path):
        conn = sqlite3.connect(db_path)
        try:
            bridge_count = conn.execute(
                "SELECT COUNT(*) FROM bridge_transfers"
            ).fetchone()[0]
            lock_count = conn.execute(
                "SELECT COUNT(*) FROM lock_ledger"
            ).fetchone()[0]
            return bridge_count, lock_count
        finally:
            conn.close()

    def test_deposit_requires_admin_key_before_creating_transfer(
        self, setup_test_db, funded_miner, monkeypatch
    ):
        """Unauthenticated deposit initiation must not lock another address."""
        bridge_api = setup_test_db["bridge_api"]
        client = self._client(bridge_api, setup_test_db["db_path"])
        monkeypatch.setenv("RC_ADMIN_KEY", "expected-admin-key")

        response = client.post(
            "/api/bridge/initiate",
            json=self._deposit_payload(funded_miner),
        )

        assert response.status_code == 401
        assert response.get_json()["error"] == "unauthorized"
        assert self._bridge_row_counts(setup_test_db["db_path"]) == (0, 0)

    def test_deposit_accepts_valid_admin_key(
        self, setup_test_db, funded_miner, monkeypatch
    ):
        """Configured admin key still allows bridge deposit initiation."""
        bridge_api = setup_test_db["bridge_api"]
        client = self._client(bridge_api, setup_test_db["db_path"])
        monkeypatch.setenv("RC_ADMIN_KEY", "expected-admin-key")

        response = client.post(
            "/api/bridge/initiate",
            headers={"X-Admin-Key": "expected-admin-key"},
            json=self._deposit_payload(funded_miner),
        )

        assert response.status_code == 200
        assert response.get_json()["ok"] is True
        assert self._bridge_row_counts(setup_test_db["db_path"]) == (1, 1)

    def test_deposit_fails_closed_when_admin_key_unconfigured(
        self, setup_test_db, funded_miner, monkeypatch
    ):
        """Bridge initiation must not become public when RC_ADMIN_KEY is unset."""
        bridge_api = setup_test_db["bridge_api"]
        client = self._client(bridge_api, setup_test_db["db_path"])
        monkeypatch.delenv("RC_ADMIN_KEY", raising=False)

        response = client.post(
            "/api/bridge/initiate",
            json=self._deposit_payload(funded_miner),
        )

        assert response.status_code == 503
        assert response.get_json()["error"] == "RC_ADMIN_KEY not configured"
        assert self._bridge_row_counts(setup_test_db["db_path"]) == (0, 0)


# =============================================================================
# Bridge Status Query Tests
# =============================================================================

class TestBridgeStatusQuery:
    """Test bridge status queries."""
    
    def test_get_by_tx_hash(self, setup_test_db, funded_miner):
        """Test querying bridge transfer by tx_hash."""
        bridge_api = setup_test_db["bridge_api"]
        conn = sqlite3.connect(setup_test_db["db_path"])
        
        req = bridge_api.BridgeTransferRequest(
            direction="deposit",
            source_chain="rustchain",
            dest_chain="solana",
            source_address=funded_miner,
            dest_address="4TRwNqXqXqXqXqXqXqXqXqXqXqXqXqXqXqXq",
            amount_rtc=10.0
        )
        
        success, result = bridge_api.create_bridge_transfer(conn, req)
        assert success is True
        tx_hash = result["tx_hash"]
        
        transfer = bridge_api.get_bridge_transfer_by_hash(conn, tx_hash)
        
        assert transfer is not None
        assert transfer["tx_hash"] == tx_hash
        assert transfer["amount_rtc"] == 10.0
        
        conn.close()
    
    def test_get_nonexistent_transfer(self, setup_test_db):
        """Test querying nonexistent transfer returns None."""
        bridge_api = setup_test_db["bridge_api"]
        conn = sqlite3.connect(setup_test_db["db_path"])
        
        transfer = bridge_api.get_bridge_transfer_by_hash(conn, "nonexistent_hash")
        
        assert transfer is None
        
        conn.close()


# =============================================================================
# Lock Ledger Tests
# =============================================================================

class TestLockLedger:
    """Test lock ledger operations."""
    
    def test_create_lock(self, setup_test_db, funded_miner):
        """Test creating a lock entry."""
        bridge_api = setup_test_db["bridge_api"]
        lock_ledger = setup_test_db["lock_ledger"]
        conn = sqlite3.connect(setup_test_db["db_path"])
        now = int(time.time())
        unlock_at = now + 3600
        
        success, result = lock_ledger.create_lock(
            conn,
            miner_id=funded_miner,
            amount_i64=10 * 1000000,
            lock_type="bridge_deposit",
            unlock_at=unlock_at
        )
        
        assert success is True
        assert result["ok"] is True
        assert result["lock_id"] > 0
        assert result["amount_rtc"] == 10.0
        
        conn.close()

    def test_database_errors_do_not_leak_details(self, setup_test_db):
        """DB failures should not expose SQLite schema details to callers."""
        lock_ledger = setup_test_db["lock_ledger"]
        conn = sqlite3.connect(":memory:")

        success, result = lock_ledger.create_lock(
            conn,
            miner_id="RTC0123456789abcdef0123456789abcdef01234567",
            amount_i64=10 * 1000000,
            lock_type="bridge_deposit",
            unlock_at=int(time.time()) + 3600
        )

        assert success is False
        assert_generic_database_error(result)

        conn.close()
    
    def test_release_lock(self, setup_test_db, funded_miner):
        """Test releasing a lock."""
        bridge_api = setup_test_db["bridge_api"]
        lock_ledger = setup_test_db["lock_ledger"]
        conn = sqlite3.connect(setup_test_db["db_path"])
        now = int(time.time())
        # Create with future unlock time, then we'll test releasing after it expires
        unlock_at = now + 1  # 1 second in future
        
        success, result = lock_ledger.create_lock(
            conn,
            miner_id=funded_miner,
            amount_i64=10 * 1000000,
            lock_type="bridge_deposit",
            unlock_at=unlock_at
        )
        assert success is True, f"Create lock failed: {result}"
        lock_id = result["lock_id"]
        
        # Wait a moment for lock to expire
        time.sleep(1.1)
        
        # Release lock (admin can release anytime, but let's test normal release)
        success, result = lock_ledger.release_lock(conn, lock_id, released_by="admin")
        
        assert success is True
        assert result["ok"] is True
        
        lock = lock_ledger.get_lock_by_id(conn, lock_id)
        assert lock.status == "released"
        
        conn.close()
    
    def test_cannot_release_early(self, setup_test_db, funded_miner):
        """Test cannot release lock before unlock time (non-admin)."""
        bridge_api = setup_test_db["bridge_api"]
        lock_ledger = setup_test_db["lock_ledger"]
        conn = sqlite3.connect(setup_test_db["db_path"])
        now = int(time.time())
        unlock_at = now + 3600
        
        success, result = lock_ledger.create_lock(
            conn,
            miner_id=funded_miner,
            amount_i64=10 * 1000000,
            lock_type="bridge_deposit",
            unlock_at=unlock_at
        )
        lock_id = result["lock_id"]
        
        success, result = lock_ledger.release_lock(conn, lock_id, released_by="system")
        
        assert success is False
        assert "not yet unlocked" in result.get("error", "")
        
        conn.close()
    
    def test_forfeit_lock(self, setup_test_db, funded_miner):
        """Test forfeiting a lock."""
        bridge_api = setup_test_db["bridge_api"]
        lock_ledger = setup_test_db["lock_ledger"]
        conn = sqlite3.connect(setup_test_db["db_path"])
        now = int(time.time())
        unlock_at = now + 3600
        
        success, result = lock_ledger.create_lock(
            conn,
            miner_id=funded_miner,
            amount_i64=10 * 1000000,
            lock_type="bridge_deposit",
            unlock_at=unlock_at
        )
        lock_id = result["lock_id"]
        
        success, result = lock_ledger.forfeit_lock(conn, lock_id, reason="penalty", forfeited_by="admin")
        
        assert success is True
        assert result["ok"] is True
        
        lock = lock_ledger.get_lock_by_id(conn, lock_id)
        assert lock.status == "forfeited"
        
        conn.close()
    
    def test_get_locks_by_miner(self, setup_test_db, funded_miner):
        """Test getting locks by miner."""
        bridge_api = setup_test_db["bridge_api"]
        lock_ledger = setup_test_db["lock_ledger"]
        conn = sqlite3.connect(setup_test_db["db_path"])
        now = int(time.time())
        
        for i in range(3):
            lock_ledger.create_lock(
                conn,
                miner_id=funded_miner,
                amount_i64=10 * 1000000,
                lock_type="bridge_deposit",
                unlock_at=now + 3600 + i
            )
        
        locks = lock_ledger.get_locks_by_miner(conn, funded_miner)
        
        assert len(locks) == 3
        
        conn.close()
    
    def test_get_miner_locked_balance(self, setup_test_db, funded_miner):
        """Test getting miner's total locked balance."""
        bridge_api = setup_test_db["bridge_api"]
        lock_ledger = setup_test_db["lock_ledger"]
        conn = sqlite3.connect(setup_test_db["db_path"])
        now = int(time.time())
        
        lock_ledger.create_lock(conn, funded_miner, 10 * 1000000, "bridge_deposit", now + 3600)
        lock_ledger.create_lock(conn, funded_miner, 20 * 1000000, "bridge_deposit", now + 3600)
        
        summary = lock_ledger.get_miner_locked_balance(conn, funded_miner)
        
        assert summary["total_locked_rtc"] == 30.0
        assert summary["total_locked_count"] == 2
        
        conn.close()

    def test_negative_limit_clamped_to_min(self, setup_test_db, funded_miner):
        """get_locks_by_miner and get_pending_unlocks must not treat negative
        limit as unbounded (SQLite LIMIT -1 = no limit)."""
        lock_ledger = setup_test_db["lock_ledger"]
        conn = sqlite3.connect(setup_test_db["db_path"])
        now = int(time.time())

        # Seed 5 locks, all locked
        for i in range(5):
            lock_ledger.create_lock(
                conn,
                miner_id=funded_miner,
                amount_i64=10 * 1000000,
                lock_type="bridge_deposit",
                unlock_at=now + 3600 + i,
            )

        # Negative limit must return at most 1 row, not all 5
        locks = lock_ledger.get_locks_by_miner(conn, funded_miner, limit=-1)
        assert len(locks) == 1

        # Also check the pending-unlocks helper with negative limit
        # Move unlock_at into the past so they become "pending"
        conn.execute(
            "UPDATE lock_ledger SET unlock_at = ? WHERE miner_id = ?",
            (now - 10, funded_miner),
        )
        conn.commit()

        pending = lock_ledger.get_pending_unlocks(conn, limit=-1)
        assert len(pending) == 1

        conn.close()



class TestLockLedgerRoutes:
    """Test lock ledger route-level validation and helper dispatch."""

    def _client(self, lock_ledger, db_path):
        lock_ledger.DB_PATH = db_path
        app = Flask(__name__)
        lock_ledger.register_lock_ledger_routes(app)
        return app.test_client()

    def _insert_locked_lock(self, db_path, miner_id, lock_id=1):
        now = int(time.time())
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """INSERT INTO lock_ledger
                   (id, miner_id, amount_i64, lock_type, locked_at, unlock_at, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (lock_id, miner_id, 5 * 1000000, "bridge_deposit", now - 3600, now + 3600, "locked", now - 3600),
            )

    def test_miner_locks_rejects_malformed_limit(self, setup_test_db, funded_miner, monkeypatch):
        lock_ledger = setup_test_db["lock_ledger"]
        monkeypatch.setenv("RC_ADMIN_KEY", "lock-admin-key")
        client = self._client(lock_ledger, setup_test_db["db_path"])

        response = client.get(f"/api/lock/miner/{funded_miner}?limit=abc", headers={"X-Admin-Key": "lock-admin-key"})

        assert response.status_code == 400
        assert response.get_json() == {"error": "limit must be an integer"}

    def test_pending_unlock_rejects_malformed_before(self, setup_test_db, monkeypatch):
        lock_ledger = setup_test_db["lock_ledger"]
        monkeypatch.setenv("RC_ADMIN_KEY", "lock-admin-key")
        client = self._client(lock_ledger, setup_test_db["db_path"])

        response = client.get("/api/lock/pending-unlock?before=not-a-timestamp", headers={"X-Admin-Key": "lock-admin-key"})

        assert response.status_code == 400
        assert response.get_json() == {"error": "before must be an integer"}

    def test_pending_unlock_route_calls_database_helper(self, setup_test_db, funded_miner, monkeypatch):
        lock_ledger = setup_test_db["lock_ledger"]
        monkeypatch.setenv("RC_ADMIN_KEY", "lock-admin-key")
        db_path = setup_test_db["db_path"]
        now = int(time.time())
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """INSERT INTO lock_ledger
                   (miner_id, amount_i64, lock_type, locked_at, unlock_at, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    funded_miner,
                    5 * 1000000,
                    "bridge_deposit",
                    now - 3600,
                    now - 60,
                    "locked",
                    now - 3600,
                ),
            )

        client = self._client(lock_ledger, db_path)

        response = client.get("/api/lock/pending-unlock?limit=10", headers={"X-Admin-Key": "lock-admin-key"})

        assert response.status_code == 200
        body = response.get_json()
        assert body["ok"] is True
        assert body["count"] == 1
        assert body["locks"][0]["miner_id"] == funded_miner

    def test_pending_unlock_before_zero_applies_cutoff(self, setup_test_db, funded_miner, monkeypatch):
        lock_ledger = setup_test_db["lock_ledger"]
        monkeypatch.setenv("RC_ADMIN_KEY", "lock-admin-key")
        db_path = setup_test_db["db_path"]
        now = int(time.time())
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """INSERT INTO lock_ledger
                   (miner_id, amount_i64, lock_type, locked_at, unlock_at, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    funded_miner,
                    5 * 1000000,
                    "bridge_deposit",
                    now - 3600,
                    now - 60,
                    "locked",
                    now - 3600,
                ),
            )

        client = self._client(lock_ledger, db_path)

        response = client.get("/api/lock/pending-unlock?before=0&limit=10", headers={"X-Admin-Key": "lock-admin-key"})

        assert response.status_code == 200
        body = response.get_json()
        assert body["ok"] is True
        assert body["count"] == 0
        assert body["locks"] == []

    @pytest.mark.parametrize("path", ["/api/lock/release", "/api/lock/forfeit"])
    def test_admin_write_routes_reject_non_object_json(self, setup_test_db, monkeypatch, path):
        lock_ledger = setup_test_db["lock_ledger"]
        client = self._client(lock_ledger, setup_test_db["db_path"])
        monkeypatch.setenv("RC_ADMIN_KEY", "expected-admin")

        response = client.post(
            path,
            headers={"X-Admin-Key": "expected-admin"},
            json=[{"lock_id": 1}],
        )

        assert response.status_code == 400
        assert response.get_json() == {"error": "JSON object required"}

    @pytest.mark.parametrize("path", ["/api/lock/release", "/api/lock/forfeit"])
    def test_admin_write_routes_reject_structured_lock_id(self, setup_test_db, monkeypatch, path):
        lock_ledger = setup_test_db["lock_ledger"]
        client = self._client(lock_ledger, setup_test_db["db_path"])
        monkeypatch.setenv("RC_ADMIN_KEY", "expected-admin")

        response = client.post(
            path,
            headers={"X-Admin-Key": "expected-admin"},
            json={"lock_id": {"id": 1}},
        )

        assert response.status_code == 400
        assert response.get_json() == {"error": "lock_id must be an integer"}

    @pytest.mark.parametrize("path", ["/api/lock/release", "/api/lock/forfeit"])
    @pytest.mark.parametrize("lock_id", [0, -1])
    def test_admin_write_routes_reject_non_positive_lock_id(self, setup_test_db, monkeypatch, path, lock_id):
        lock_ledger = setup_test_db["lock_ledger"]
        client = self._client(lock_ledger, setup_test_db["db_path"])
        monkeypatch.setenv("RC_ADMIN_KEY", "expected-admin")

        response = client.post(
            path,
            headers={"X-Admin-Key": "expected-admin"},
            json={"lock_id": lock_id},
        )

        assert response.status_code == 400
        assert response.get_json() == {"error": "lock_id must be positive"}

    @pytest.mark.parametrize("path", ["/api/lock/release", "/api/lock/forfeit"])
    @pytest.mark.parametrize("lock_id", [True, False])
    def test_admin_write_routes_reject_boolean_lock_id(self, setup_test_db, monkeypatch, path, lock_id):
        lock_ledger = setup_test_db["lock_ledger"]
        client = self._client(lock_ledger, setup_test_db["db_path"])
        monkeypatch.setenv("RC_ADMIN_KEY", "expected-admin")

        response = client.post(
            path,
            headers={"X-Admin-Key": "expected-admin"},
            json={"lock_id": lock_id},
        )

        assert response.status_code == 400
        assert response.get_json() == {"error": "lock_id must be an integer"}

    def test_release_route_rejects_structured_tx_hash(self, setup_test_db, funded_miner, monkeypatch):
        lock_ledger = setup_test_db["lock_ledger"]
        db_path = setup_test_db["db_path"]
        self._insert_locked_lock(db_path, funded_miner)
        client = self._client(lock_ledger, db_path)
        monkeypatch.setenv("RC_ADMIN_KEY", "expected-admin")

        response = client.post(
            "/api/lock/release",
            headers={"X-Admin-Key": "expected-admin"},
            json={"lock_id": 1, "release_tx_hash": {"tx": "abc"}},
        )

        assert response.status_code == 400
        assert response.get_json() == {"error": "release_tx_hash must be a string"}

    def test_release_route_treats_whitespace_tx_hash_as_empty(self, setup_test_db, funded_miner, monkeypatch):
        lock_ledger = setup_test_db["lock_ledger"]
        db_path = setup_test_db["db_path"]
        self._insert_locked_lock(db_path, funded_miner)
        client = self._client(lock_ledger, db_path)
        monkeypatch.setenv("RC_ADMIN_KEY", "expected-admin")

        response = client.post(
            "/api/lock/release",
            headers={"X-Admin-Key": "expected-admin"},
            json={"lock_id": 1, "release_tx_hash": "   "},
        )

        assert response.status_code == 200
        assert response.get_json()["release_tx_hash"] is None
        with sqlite3.connect(db_path) as conn:
            stored = conn.execute("SELECT release_tx_hash FROM lock_ledger WHERE id = 1").fetchone()[0]
        assert stored is None

    def test_forfeit_route_rejects_structured_reason(self, setup_test_db, funded_miner, monkeypatch):
        lock_ledger = setup_test_db["lock_ledger"]
        db_path = setup_test_db["db_path"]
        self._insert_locked_lock(db_path, funded_miner)
        client = self._client(lock_ledger, db_path)
        monkeypatch.setenv("RC_ADMIN_KEY", "expected-admin")

        response = client.post(
            "/api/lock/forfeit",
            headers={"X-Admin-Key": "expected-admin"},
            json={"lock_id": 1, "reason": ["bad"]},
        )

        assert response.status_code == 400
        assert response.get_json() == {"error": "reason must be a string"}

    def test_forfeit_route_treats_whitespace_reason_as_default(self, setup_test_db, funded_miner, monkeypatch):
        lock_ledger = setup_test_db["lock_ledger"]
        db_path = setup_test_db["db_path"]
        self._insert_locked_lock(db_path, funded_miner)
        client = self._client(lock_ledger, db_path)
        monkeypatch.setenv("RC_ADMIN_KEY", "expected-admin")

        response = client.post(
            "/api/lock/forfeit",
            headers={"X-Admin-Key": "expected-admin"},
            json={"lock_id": 1, "reason": "   "},
        )

        assert response.status_code == 200
        assert response.get_json()["reason"] == "admin_forfeit"


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests for bridge + lock ledger."""
    
    def test_full_deposit_flow(self, setup_test_db, funded_miner):
        """Test complete deposit flow: create -> confirm -> release."""
        bridge_api = setup_test_db["bridge_api"]
        lock_ledger = setup_test_db["lock_ledger"]
        conn = sqlite3.connect(setup_test_db["db_path"])
        
        # 1. Initiate deposit
        req = bridge_api.BridgeTransferRequest(
            direction="deposit",
            source_chain="rustchain",
            dest_chain="solana",
            source_address=funded_miner,
            dest_address="4TRwNqXqXqXqXqXqXqXqXqXqXqXqXqXqXqXq",
            amount_rtc=10.0
        )
        
        success, result = bridge_api.create_bridge_transfer(conn, req)
        assert success is True
        tx_hash = result["tx_hash"]
        
        # 2. Verify lock created
        locks = lock_ledger.get_locks_by_miner(conn, funded_miner)
        assert len(locks) == 1
        assert locks[0].status == "locked"
        
        # 3. Update external confirmations
        success, result = bridge_api.update_external_confirmation(
            conn, tx_hash,
            external_tx_hash="ext_tx_123",
            confirmations=12
        )
        assert success is True
        assert result["status"] == "completed"
        
        # 4. Verify lock released
        locks = lock_ledger.get_locks_by_miner(conn, funded_miner)
        assert len(locks) == 1
        assert locks[0].status == "released"

        conn.close()

    def test_deposit_create_hard_debits_source(self, setup_test_db, funded_miner):
        """Debit-on-lock: an outbound deposit debits the source AT CREATE, and
        completion makes no further balance change (it's already gone)."""
        bridge_api = setup_test_db["bridge_api"]
        conn = sqlite3.connect(setup_test_db["db_path"])

        def source_balance():
            return conn.execute(
                "SELECT amount_i64 FROM balances WHERE miner_id = ?",
                (funded_miner,),
            ).fetchone()[0]

        start_balance = source_balance()  # 100 RTC
        amount_i64 = bridge_api.parse_bridge_amount_i64(10.0)

        req = bridge_api.BridgeTransferRequest(
            direction="deposit",
            source_chain="rustchain",
            dest_chain="solana",
            source_address=funded_miner,
            dest_address="4TRwNqXqXqXqXqXqXqXqXqXqXqXqXqXqXq",
            amount_rtc=10.0,
        )
        success, result = bridge_api.create_bridge_transfer(conn, req)
        assert success is True
        tx_hash = result["tx_hash"]

        # Hard-debited immediately at create.
        assert source_balance() == start_balance - amount_i64

        success, result = bridge_api.update_external_confirmation(
            conn, tx_hash, external_tx_hash="ext_tx_debit", confirmations=12
        )
        assert success is True
        assert result["status"] == "completed"

        # Completion is a no-op for balance — funds already left at create.
        assert source_balance() == start_balance - amount_i64

        conn.close()

    def test_deposit_lock_self_enforces_against_raw_balance_gate(self, setup_test_db, funded_miner):
        """The whole point of debit-on-lock: any gate that reads raw amount_i64
        (withdrawal, governance, transfers) automatically sees the locked funds
        gone — no per-gate reservation check needed. We simulate such a gate by
        reading the raw balance the same way they do."""
        bridge_api = setup_test_db["bridge_api"]
        conn = sqlite3.connect(setup_test_db["db_path"])

        def raw_spendable():
            # Exactly what withdrawal/governance read: balances.amount_i64.
            return conn.execute(
                "SELECT amount_i64 FROM balances WHERE miner_id = ?",
                (funded_miner,),
            ).fetchone()[0]

        assert raw_spendable() == 100 * 1000000

        req = bridge_api.BridgeTransferRequest(
            direction="deposit", source_chain="rustchain", dest_chain="solana",
            source_address=funded_miner,
            dest_address="4TRwNqXqXqXqXqXqXqXqXqXqXqXqXqXqXq",
            amount_rtc=80.0,
        )
        success, _ = bridge_api.create_bridge_transfer(conn, req)
        assert success is True

        # A withdrawal/governance gate reading raw balance now sees only 20 RTC
        # — it cannot drain the 80 RTC locked for the pending bridge deposit.
        assert raw_spendable() == 20 * 1000000
        conn.close()

    def test_deposit_create_rejects_insufficient_source(self, setup_test_db):
        """Cannot hard-lock funds that don't exist: create fails closed and never
        drives the source negative."""
        bridge_api = setup_test_db["bridge_api"]
        conn = sqlite3.connect(setup_test_db["db_path"])

        source = "RTC0123456789abcdef0123456789abcdef0123dead"
        conn.execute(
            "INSERT INTO balances (miner_id, amount_i64) VALUES (?, ?)",
            (source, 5 * 1000000),  # only 5 RTC
        )
        conn.commit()

        req = bridge_api.BridgeTransferRequest(
            direction="deposit", source_chain="rustchain", dest_chain="solana",
            source_address=source,
            dest_address="4TRwNqXqXqXqXqXqXqXqXqXqXqXqXqXqXq",
            amount_rtc=10.0,  # exceeds 5 RTC
        )
        success, result = bridge_api.create_bridge_transfer(conn, req, admin_initiated=True)
        assert success is False
        assert "Insufficient available balance" in result.get("error", "")
        bal = conn.execute(
            "SELECT amount_i64 FROM balances WHERE miner_id = ?", (source,)
        ).fetchone()[0]
        assert bal == 5 * 1000000  # untouched
        conn.close()

    def test_deposit_void_refunds_source(self, setup_test_db, funded_miner):
        """Voiding a hard-debited deposit must refund the source exactly once."""
        bridge_api = setup_test_db["bridge_api"]
        conn = sqlite3.connect(setup_test_db["db_path"])

        def source_balance():
            return conn.execute(
                "SELECT amount_i64 FROM balances WHERE miner_id = ?",
                (funded_miner,),
            ).fetchone()[0]

        start = source_balance()
        amount_i64 = bridge_api.parse_bridge_amount_i64(30.0)

        req = bridge_api.BridgeTransferRequest(
            direction="deposit", source_chain="rustchain", dest_chain="solana",
            source_address=funded_miner,
            dest_address="4TRwNqXqXqXqXqXqXqXqXqXqXqXqXqXqXq",
            amount_rtc=30.0,
        )
        success, result = bridge_api.create_bridge_transfer(conn, req)
        assert success is True
        tx_hash = result["tx_hash"]
        assert source_balance() == start - amount_i64

        ok, _ = bridge_api.void_bridge_transfer(conn, tx_hash, "test", "tester")
        assert ok is True
        assert source_balance() == start  # fully refunded

        # Cannot void again (status guard) — no double refund.
        ok, _ = bridge_api.void_bridge_transfer(conn, tx_hash, "test", "tester")
        assert ok is False
        assert source_balance() == start

        conn.close()

    def test_migration_debits_legacy_pending_deposit(self, setup_test_db, funded_miner):
        """A deposit left from the legacy reservation model (source_debited=0)
        gets hard-debited exactly once by the migration; re-running is a no-op."""
        bridge_api = setup_test_db["bridge_api"]
        conn = sqlite3.connect(setup_test_db["db_path"])
        cur = conn.cursor()

        amount_i64 = 40 * 1000000
        # Simulate a legacy pending deposit that was never debited.
        cur.execute("""
            INSERT INTO bridge_transfers (
                direction, source_chain, dest_chain, source_address, dest_address,
                amount_i64, amount_rtc, bridge_type, status, lock_epoch,
                created_at, updated_at, tx_hash, source_debited
            ) VALUES ('deposit','rustchain','solana',?,?,?,?, 'bottube','locked',0,
                      0,0,?,0)
        """, (funded_miner, "4TRwNqXqXqXqXqXqXqXqXqXqXqXqXqXqXq", amount_i64, 40.0,
              "legacy_tx_hash_1"))
        conn.commit()

        start = conn.execute("SELECT amount_i64 FROM balances WHERE miner_id=?",
                             (funded_miner,)).fetchone()[0]

        bridge_api.migrate_deposits_to_hard_locks(cur)
        conn.commit()
        after = conn.execute("SELECT amount_i64 FROM balances WHERE miner_id=?",
                             (funded_miner,)).fetchone()[0]
        assert after == start - amount_i64
        assert cur.execute(
            "SELECT source_debited FROM bridge_transfers WHERE tx_hash='legacy_tx_hash_1'"
        ).fetchone()[0] == 1

        # Idempotent: a second run debits nothing further.
        bridge_api.migrate_deposits_to_hard_locks(cur)
        conn.commit()
        assert conn.execute("SELECT amount_i64 FROM balances WHERE miner_id=?",
                            (funded_miner,)).fetchone()[0] == after

        conn.close()

    def _insert_legacy_undebited_deposit(self, conn, source, amount_i64, tx_hash):
        """A deposit row the migration could NOT debit — source_debited stays 0."""
        conn.execute("""
            INSERT INTO bridge_transfers (
                direction, source_chain, dest_chain, source_address, dest_address,
                amount_i64, amount_rtc, bridge_type, status, lock_epoch,
                created_at, updated_at, expires_at, tx_hash, source_debited
            ) VALUES ('deposit','rustchain','solana',?,?,?,?, 'bottube','confirming',0,
                      0,0,?,?,0)
        """, (source, "4TRwNqXqXqXqXqXqXqXqXqXqXqXqXqXqXq", amount_i64, amount_i64 / 1000000,
              int(time.time()) + 3600, tx_hash))
        conn.commit()

    def test_completion_safety_net_debits_undebited_deposit(self, setup_test_db, funded_miner):
        """A deposit that reaches completion still source_debited=0 (migration
        couldn't settle it) must be debited at completion, never completed free."""
        bridge_api = setup_test_db["bridge_api"]
        conn = sqlite3.connect(setup_test_db["db_path"])
        amount_i64 = 25 * 1000000
        self._insert_legacy_undebited_deposit(conn, funded_miner, amount_i64, "legacy_complete_1")
        start = conn.execute("SELECT amount_i64 FROM balances WHERE miner_id=?",
                             (funded_miner,)).fetchone()[0]

        ok, result = bridge_api.update_external_confirmation(
            conn, "legacy_complete_1", external_tx_hash="ext1", confirmations=12
        )
        assert ok is True and result["status"] == "completed"
        # Debited at completion by the safety net.
        assert conn.execute("SELECT amount_i64 FROM balances WHERE miner_id=?",
                            (funded_miner,)).fetchone()[0] == start - amount_i64
        conn.close()

    def test_completion_safety_net_fails_closed_when_source_drained(self, setup_test_db):
        """If an undebited deposit's source can't cover settlement at completion,
        fail closed — do NOT complete, do NOT mint a negative balance."""
        bridge_api = setup_test_db["bridge_api"]
        conn = sqlite3.connect(setup_test_db["db_path"])
        source = "RTC0123456789abcdef0123456789abcdef0123dead"
        conn.execute("INSERT INTO balances (miner_id, amount_i64) VALUES (?, ?)",
                     (source, 5 * 1000000))
        self._insert_legacy_undebited_deposit(conn, source, 30 * 1000000, "legacy_complete_2")

        ok, result = bridge_api.update_external_confirmation(
            conn, "legacy_complete_2", external_tx_hash="ext2", confirmations=12
        )
        assert ok is False
        assert conn.execute("SELECT amount_i64 FROM balances WHERE miner_id=?",
                            (source,)).fetchone()[0] == 5 * 1000000  # untouched
        transfer = bridge_api.get_bridge_transfer_by_hash(conn, "legacy_complete_2")
        assert transfer["status"] != "completed"
        conn.close()

    def test_external_confirmation_rejects_lowered_required_threshold(self, setup_test_db, funded_miner):
        """Bridge callbacks must not lower the stored confirmation threshold."""
        bridge_api = setup_test_db["bridge_api"]
        lock_ledger = setup_test_db["lock_ledger"]
        conn = sqlite3.connect(setup_test_db["db_path"])

        req = bridge_api.BridgeTransferRequest(
            direction="deposit",
            source_chain="rustchain",
            dest_chain="solana",
            source_address=funded_miner,
            dest_address="4TRwNqXqXqXqXqXqXqXqXqXqXqXqXqXqXq",
            amount_rtc=10.0
        )
        success, result = bridge_api.create_bridge_transfer(conn, req)
        assert success is True
        tx_hash = result["tx_hash"]

        success, result = bridge_api.update_external_confirmation(
            conn,
            tx_hash,
            external_tx_hash="ext_tx_threshold",
            confirmations=1,
            required_confirmations=1,
        )

        assert success is False
        assert result["error"] == "required_confirmations cannot be lowered"
        locks = lock_ledger.get_locks_by_miner(conn, funded_miner)
        assert locks[0].status == "locked"
        transfer = bridge_api.get_bridge_transfer_by_hash(conn, tx_hash)
        assert transfer["status"] == "pending"
        assert transfer["required_confirmations"] == bridge_api.BRIDGE_DEFAULT_CONFIRMATIONS
        conn.close()

    def test_external_confirmation_helper_rejects_unbounded_counts(self, setup_test_db, funded_miner):
        """Core helper enforces bounds even when bypassing the HTTP parser."""
        bridge_api = setup_test_db["bridge_api"]
        lock_ledger = setup_test_db["lock_ledger"]
        conn = sqlite3.connect(setup_test_db["db_path"])

        req = bridge_api.BridgeTransferRequest(
            direction="deposit",
            source_chain="rustchain",
            dest_chain="solana",
            source_address=funded_miner,
            dest_address="4TRwNqXqXqXqXqXqXqXqXqXqXqXqXqXqXq",
            amount_rtc=10.0
        )
        success, result = bridge_api.create_bridge_transfer(conn, req)
        assert success is True
        tx_hash = result["tx_hash"]

        success, result = bridge_api.update_external_confirmation(
            conn,
            tx_hash,
            external_tx_hash="ext_tx_unbounded",
            confirmations=bridge_api.BRIDGE_MAX_CONFIRMATIONS + 1,
        )

        assert success is False
        assert result["error"] == (
            f"confirmations must be between 0 and {bridge_api.BRIDGE_MAX_CONFIRMATIONS}"
        )
        locks = lock_ledger.get_locks_by_miner(conn, funded_miner)
        assert locks[0].status == "locked"
        transfer = bridge_api.get_bridge_transfer_by_hash(conn, tx_hash)
        assert transfer["status"] == "pending"
        conn.close()

    def test_void_releases_lock(self, setup_test_db, funded_miner):
        """Test that voiding a transfer releases the lock."""
        bridge_api = setup_test_db["bridge_api"]
        lock_ledger = setup_test_db["lock_ledger"]
        conn = sqlite3.connect(setup_test_db["db_path"])
        
        req = bridge_api.BridgeTransferRequest(
            direction="deposit",
            source_chain="rustchain",
            dest_chain="solana",
            source_address=funded_miner,
            dest_address="4TRwNqXqXqXqXqXqXqXqXqXqXqXqXqXqXqXq",
            amount_rtc=10.0
        )
        
        success, result = bridge_api.create_bridge_transfer(conn, req)
        tx_hash = result["tx_hash"]
        
        success, result = bridge_api.void_bridge_transfer(
            conn, tx_hash,
            reason="user_request",
            voided_by="admin"
        )
        assert success is True
        
        locks = lock_ledger.get_locks_by_miner(conn, funded_miner)
        assert len(locks) == 1
        assert locks[0].status == "released"
        
        conn.close()

    def test_stale_void_cannot_overwrite_completed_withdraw(
        self, setup_test_db, monkeypatch
    ):
        """A stale admin void must not overwrite a completed withdraw."""
        bridge_api = setup_test_db["bridge_api"]
        conn = sqlite3.connect(setup_test_db["db_path"])

        req = bridge_api.BridgeTransferRequest(
            direction="withdraw",
            source_chain="solana",
            dest_chain="rustchain",
            source_address="4TRwNqXqXqXqXqXqXqXqXqXqXqXqXqXqXq",
            dest_address="RTCwithdrawdest",
            amount_rtc=10.0,
        )
        success, result = bridge_api.create_bridge_transfer(conn, req)
        assert success is True
        tx_hash = result["tx_hash"]

        stale_transfer = bridge_api.get_bridge_transfer_by_hash(conn, tx_hash)
        success, result = bridge_api.update_external_confirmation(
            conn,
            tx_hash,
            external_tx_hash="solana_tx_complete",
            confirmations=12,
            required_confirmations=12,
        )
        assert success is True
        assert result["status"] == "completed"

        original_get_bridge_transfer_by_hash = bridge_api.get_bridge_transfer_by_hash

        def stale_once(_conn, current_tx_hash):
            if current_tx_hash == tx_hash:
                return stale_transfer
            return original_get_bridge_transfer_by_hash(_conn, current_tx_hash)

        monkeypatch.setattr(bridge_api, "get_bridge_transfer_by_hash", stale_once)

        success, result = bridge_api.void_bridge_transfer(
            conn,
            tx_hash,
            reason="late_admin_void",
            voided_by="admin",
        )

        assert success is False
        assert result["error"] == "Cannot void transfer with status 'completed'"

        transfer = original_get_bridge_transfer_by_hash(conn, tx_hash)
        assert transfer["status"] == "completed"
        assert transfer["voided_by"] is None
        balance_i64 = conn.execute(
            "SELECT amount_i64 FROM balances WHERE miner_id = ?",
            ("RTCwithdrawdest",),
        ).fetchone()[0]
        assert balance_i64 == 10 * bridge_api.BRIDGE_UNIT

        conn.close()


class TestBridgeCallbackAuth:
    """Test bridge service callback authentication."""

    def _client(self, bridge_api):
        app = Flask(__name__)
        bridge_api.register_bridge_routes(app)
        return app.test_client()

    def test_update_external_fails_closed_when_api_key_unconfigured(
        self, setup_test_db, monkeypatch
    ):
        bridge_api = setup_test_db["bridge_api"]
        client = self._client(bridge_api)
        monkeypatch.delenv("RC_BRIDGE_API_KEY", raising=False)

        response = client.post(
            "/api/bridge/update-external",
            json={"tx_hash": "bridge_tx", "external_tx_hash": "external_tx"},
        )

        assert response.status_code == 503
        assert response.get_json()["error"] == "Bridge API key not configured"

    def test_update_external_uses_constant_time_api_key_compare(
        self, setup_test_db, monkeypatch
    ):
        bridge_api = setup_test_db["bridge_api"]
        client = self._client(bridge_api)
        monkeypatch.setenv("RC_BRIDGE_API_KEY", "expected-key")
        calls = []

        def fake_compare(provided, expected):
            calls.append((provided, expected))
            return False

        monkeypatch.setattr(bridge_api.hmac, "compare_digest", fake_compare)

        response = client.post(
            "/api/bridge/update-external",
            headers={"X-API-Key": "wrong-key"},
            json={"tx_hash": "bridge_tx", "external_tx_hash": "external_tx"},
        )

        assert response.status_code == 401
        assert calls == [("wrong-key", "expected-key")]

    def test_update_external_accepts_configured_api_key_before_payload_validation(
        self, setup_test_db, monkeypatch
    ):
        bridge_api = setup_test_db["bridge_api"]
        client = self._client(bridge_api)
        monkeypatch.setenv("RC_BRIDGE_API_KEY", "expected-key")

        response = client.post(
            "/api/bridge/update-external",
            headers={"X-API-Key": "expected-key"},
        )

        assert response.status_code == 400
        assert response.get_json()["error"] == "Request body required"

    def test_update_external_rejects_non_object_json_before_state_handling(
        self, setup_test_db, monkeypatch
    ):
        bridge_api = setup_test_db["bridge_api"]
        client = self._client(bridge_api)
        monkeypatch.setenv("RC_BRIDGE_API_KEY", "expected-key")

        response = client.post(
            "/api/bridge/update-external",
            headers={"X-API-Key": "expected-key"},
            json=["not", "an", "object"],
        )

        assert response.status_code == 400
        assert response.get_json()["error"] == "Request body required"

    def test_void_bridge_rejects_non_object_json_before_state_handling(
        self, setup_test_db, monkeypatch
    ):
        bridge_api = setup_test_db["bridge_api"]
        client = self._client(bridge_api)
        monkeypatch.setenv("RC_ADMIN_KEY", "expected-key")

        response = client.post(
            "/api/bridge/void",
            headers={"X-Admin-Key": "expected-key"},
            json=["not", "an", "object"],
        )

        assert response.status_code == 400
        assert response.get_json()["error"] == "Request body required"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
