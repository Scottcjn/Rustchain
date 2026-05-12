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
            memo TEXT
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
        ("RTC_test_miner", 100 * 1000000)  # 100 RTC
    )
    conn.commit()
    conn.close()
    return "RTC_test_miner"


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
        valid, msg = bridge_api.validate_chain_address_format("rustchain", "RTC_test123abc")
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
    
    def test_admin_bypasses_balance_check(self, setup_test_db):
        """Test admin-initiated transfer bypasses balance check."""
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
        
        assert success is True
        assert result["ok"] is True
        
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
            miner_id="RTC_test_miner",
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


class TestLockLedgerRoutes:
    """Test lock ledger Flask routes."""

    def _client(self, lock_ledger, db_path: str):
        app = Flask(__name__)
        lock_ledger.DB_PATH = db_path
        lock_ledger.register_lock_ledger_routes(app)
        return app.test_client()

    def test_get_miner_locks_returns_400_for_invalid_limit(self, setup_test_db, funded_miner):
        lock_ledger = setup_test_db["lock_ledger"]
        client = self._client(lock_ledger, setup_test_db["db_path"])

        response = client.get(f"/api/lock/miner/{funded_miner}?limit=abc")

        assert response.status_code == 400
        assert response.get_json()["error"] == "Invalid limit query parameter"

    def test_get_pending_unlocks_returns_400_for_invalid_before(self, setup_test_db):
        lock_ledger = setup_test_db["lock_ledger"]
        client = self._client(lock_ledger, setup_test_db["db_path"])

        response = client.get("/api/lock/pending-unlock?before=not-a-timestamp")

        assert response.status_code == 400
        assert response.get_json()["error"] == "Invalid before query parameter"

    def test_get_pending_unlocks_honors_zero_before_cutoff(self, setup_test_db, funded_miner):
        lock_ledger = setup_test_db["lock_ledger"]
        client = self._client(lock_ledger, setup_test_db["db_path"])
        conn = sqlite3.connect(setup_test_db["db_path"])
        now = int(time.time())

        conn.execute(
            """
            INSERT INTO lock_ledger (
                bridge_transfer_id,
                miner_id,
                amount_i64,
                lock_type,
                locked_at,
                unlock_at,
                status,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'locked', ?)
            """,
            (None, funded_miner, 5 * 1000000, "bridge_deposit", now - 60, now - 5, now - 60),
        )
        conn.commit()
        conn.close()

        response = client.get("/api/lock/pending-unlock?before=0")

        assert response.status_code == 200
        payload = response.get_json()
        assert payload["ok"] is True
        assert payload["count"] == 0
        assert payload["locks"] == []

    def test_get_pending_unlocks_route_returns_expired_locks(self, setup_test_db, funded_miner):
        lock_ledger = setup_test_db["lock_ledger"]
        client = self._client(lock_ledger, setup_test_db["db_path"])
        conn = sqlite3.connect(setup_test_db["db_path"])
        now = int(time.time())

        conn.execute(
            """
            INSERT INTO lock_ledger (
                bridge_transfer_id,
                miner_id,
                amount_i64,
                lock_type,
                locked_at,
                unlock_at,
                status,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'locked', ?)
            """,
            (None, funded_miner, 5 * 1000000, "bridge_deposit", now - 60, now - 5, now - 60),
        )
        conn.commit()
        conn.close()

        response = client.get("/api/lock/pending-unlock")

        assert response.status_code == 200
        payload = response.get_json()
        assert payload["ok"] is True
        assert payload["count"] == 1
        assert payload["locks"][0]["miner_id"] == funded_miner


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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
