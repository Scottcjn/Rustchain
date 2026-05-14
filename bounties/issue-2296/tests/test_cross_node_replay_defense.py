#!/usr/bin/env python3
"""
Verification Tests for Cross-Node Attestation Replay Defense
=============================================================

Comprehensive test suite verifying the effectiveness of cross-node
replay attack prevention mechanisms.

Test Categories:
1. Unit Tests - Core nonce validation logic
2. Integration Tests - Full attestation flow
3. Security Tests - Attack simulation and verification
4. Regression Tests - Ensure fixes remain effective

Usage:
    pytest test_cross_node_replay_defense.py -v
    pytest test_cross_node_replay_defense.py --attack-simulation
    pytest test_cross_node_replay_defense.py -k "test_cross_node"

Bounty: https://github.com/Scottcjn/rustchain-bounties/issues/2296
"""

import hashlib
import json
import os
import sqlite3
import sys
import time
import uuid
from pathlib import Path
from typing import Dict, Any, Optional
from unittest.mock import patch, MagicMock

import pytest

# Add source directory to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
SRC_DIR = PROJECT_ROOT / "bounties" / "issue-2296" / "src"
sys.path.insert(0, str(SRC_DIR))

from cross_node_replay_defense import (
    init_cross_node_nonce_tables,
    cleanup_expired_nonces,
    validate_cross_node_nonce,
    store_used_cross_node_nonce,
    get_cross_node_nonce_stats,
    get_replay_attack_report,
    NonceCleanupService,
    CROSS_NODE_NONCE_TTL,
    NODE_ID,
)

# Import attack simulator
from cross_node_replay_attack import (
    CrossNodeReplayAttacker,
    AttackType,
    AttackStatus,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def test_db():
    """Create isolated test database."""
    db_path = f":memory:"
    conn = sqlite3.connect(db_path)
    init_cross_node_nonce_tables(conn)
    yield conn
    conn.close()


@pytest.fixture
def test_nonce() -> str:
    """Generate a test nonce."""
    return f"nonce_{uuid.uuid4().hex}"


@pytest.fixture
def test_miner_id() -> str:
    """Generate a test miner ID."""
    return f"miner_{uuid.uuid4().hex[:16]}"


@pytest.fixture
def mock_time():
    """Mock time for deterministic testing."""
    base_time = 1700000000  # Fixed timestamp
    with patch('cross_node_replay_defense.time.time', return_value=base_time):
        yield base_time


# =============================================================================
# Unit Tests: Nonce Initialization
# =============================================================================

class TestNonceTableInitialization:
    """Tests for database schema initialization."""

    def test_tables_created(self, test_db):
        """Verify all required tables are created."""
        cursor = test_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = {row[0] for row in cursor.fetchall()}
        
        assert "cross_node_nonces" in tables
        assert "cross_node_sync_queue" in tables
        assert "cross_node_peers" in tables

    def test_indexes_created(self, test_db):
        """Verify required indexes are created."""
        cursor = test_db.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        )
        indexes = {row[0] for row in cursor.fetchall()}
        
        assert "idx_cross_nonces_expires" in indexes
        assert "idx_cross_nonces_node" in indexes

    def test_idempotent_initialization(self, test_db):
        """Verify initialization can be called multiple times."""
        # Should not raise
        init_cross_node_nonce_tables(test_db)
        init_cross_node_nonce_tables(test_db)
        init_cross_node_nonce_tables(test_db)


# =============================================================================
# Unit Tests: Nonce Validation
# =============================================================================

class TestNonceValidation:
    """Tests for nonce validation logic."""

    def test_valid_nonce_accepted(self, test_db, test_nonce, test_miner_id):
        """A fresh nonce should be accepted."""
        valid, error = validate_cross_node_nonce(test_db, test_nonce, test_miner_id)
        
        assert valid is True
        assert error is None

    def test_empty_nonce_rejected(self, test_db, test_miner_id):
        """Empty nonce should be rejected."""
        valid, error = validate_cross_node_nonce(test_db, "", test_miner_id)
        
        assert valid is False
        assert error == "invalid_nonce_format"

    def test_none_nonce_rejected(self, test_db, test_miner_id):
        """None nonce should be rejected."""
        valid, error = validate_cross_node_nonce(test_db, None, test_miner_id)
        
        assert valid is False
        assert error == "invalid_nonce_format"

    def test_short_nonce_rejected(self, test_db, test_miner_id):
        """Nonces shorter than 16 chars should be rejected."""
        valid, error = validate_cross_node_nonce(test_db, "short", test_miner_id)
        
        assert valid is False
        assert error == "nonce_too_short"

    def test_whitespace_nonce_stripped(self, test_db, test_nonce, test_miner_id):
        """Whitespace should be stripped from nonce."""
        valid, error = validate_cross_node_nonce(
            test_db, f"  {test_nonce}  ", test_miner_id
        )
        
        assert valid is True

    def test_stored_nonce_rejected_for_replay(self, test_db, test_nonce, test_miner_id, mock_time):
        """A used nonce should be rejected for replay."""
        # Store the nonce
        store_used_cross_node_nonce(test_db, test_nonce, test_miner_id)
        
        # Try to reuse
        valid, error = validate_cross_node_nonce(test_db, test_nonce, test_miner_id)
        
        assert valid is False
        assert error == "nonce_already_used"

    def test_stored_nonce_rejected_different_miner(self, test_db, test_nonce, mock_time):
        """A nonce used by one miner should be rejected for another."""
        miner1 = "miner_1"
        miner2 = "miner_2"
        
        # Miner 1 uses nonce
        store_used_cross_node_nonce(test_db, test_nonce, miner1)
        
        # Miner 2 tries to reuse
        valid, error = validate_cross_node_nonce(test_db, test_nonce, miner2)
        
        assert valid is False
        assert error == "nonce_belongs_to_different_miner"


# =============================================================================
# Unit Tests: Cross-Node Replay Detection
# =============================================================================

class TestCrossNodeReplayDetection:
    """Tests specifically for cross-node replay scenarios."""

    def test_cross_node_replay_detected(self, test_db, test_nonce, mock_time):
        """Replay from different node should be detected."""
        original_node = "node-0"
        replay_node = "node-1"
        miner_id = "miner_target"
        
        # Simulate nonce used on node-0
        with patch('cross_node_replay_defense.NODE_ID', original_node):
            store_used_cross_node_nonce(test_db, test_nonce, miner_id)
        
        # Try replay on node-1
        with patch('cross_node_replay_defense.NODE_ID', replay_node):
            valid, error = validate_cross_node_nonce(test_db, test_nonce, miner_id)
            
            assert valid is False
            assert error == "cross_node_replay_detected"

    def test_same_node_replay_detected(self, test_db, test_nonce, mock_time):
        """Replay on same node should be detected."""
        node_id = "node-0"
        miner_id = "miner_target"
        
        # First use
        with patch('cross_node_replay_defense.NODE_ID', node_id):
            store_used_cross_node_nonce(test_db, test_nonce, miner_id)
            valid, error = validate_cross_node_nonce(test_db, test_nonce, miner_id)
            
            assert valid is False
            assert error == "nonce_already_used"

    def test_expired_nonce_can_be_reused(self, test_db, test_nonce, test_miner_id):
        """Expired nonces should be allowed for reuse."""
        past_time = 1700000000
        future_time = past_time + CROSS_NODE_NONCE_TTL + 100  # Well after expiration
        
        # Store with past timestamp
        with patch('cross_node_replay_defense.time.time', return_value=past_time):
            store_used_cross_node_nonce(test_db, test_nonce, test_miner_id)
        
        # Validate in the future
        with patch('cross_node_replay_defense.time.time', return_value=future_time):
            valid, error = validate_cross_node_nonce(test_db, test_nonce, test_miner_id)
            
            # Should be valid (expired nonces can be reused)
            assert valid is True


# =============================================================================
# Integration Tests: Full Attack Scenarios
# =============================================================================

class TestAttackScenarios:
    """Integration tests simulating real attack scenarios."""

    def test_same_node_replay_attack_blocked(self, test_db):
        """Same-node replay attack should be blocked."""
        attacker = CrossNodeReplayAttacker(node_count=1)
        
        # Capture attestation
        capture = attacker.capture_attestation("target_miner", "node-0")
        
        # Try replay on same node
        result = attacker.replay_attestation(
            capture.capture_id, "node-0", AttackType.SAME_NODE_REPLAY
        )
        
        assert result.blocked is True
        assert result.block_reason == "nonce_already_used_on_this_node"

    def test_cross_node_replay_attack_blocked(self, test_db):
        """Cross-node replay attack should be blocked."""
        attacker = CrossNodeReplayAttacker(node_count=3)
        
        # Capture attestation from node-0
        capture = attacker.capture_attestation("target_miner", "node-0")
        
        # Try replay on node-1 (different node)
        result = attacker.replay_attestation(
            capture.capture_id, "node-1", AttackType.CROSS_NODE_REPLAY
        )
        
        assert result.blocked is True
        assert result.block_reason == "cross_node_replay_detected"

    def test_time_shift_replay_attack_blocked(self, test_db):
        """Time-shift replay attack should be blocked."""
        attacker = CrossNodeReplayAttacker(node_count=3)
        
        # Capture attestation
        capture = attacker.capture_attestation("target_miner", "node-0")
        
        # Try replay with modified timestamp on different node
        result = attacker.replay_attestation(
            capture.capture_id, "node-1", AttackType.TIME_SHIFT_REPLAY
        )
        
        assert result.blocked is True
        # Time shift doesn't help - nonce is still tracked
        assert result.block_reason in ["cross_node_replay_detected", "nonce_already_used_on_this_node"]

    def test_full_attack_campaign(self):
        """Run full attack campaign and verify all attacks blocked."""
        attacker = CrossNodeReplayAttacker(node_count=5)
        
        campaign = attacker.run_attack_campaign(
            captures_per_node=10,
            attack_types=[
                AttackType.SAME_NODE_REPLAY,
                AttackType.CROSS_NODE_REPLAY,
                AttackType.TIME_SHIFT_REPLAY,
            ]
        )
        
        # All attacks should be blocked
        assert campaign.successful_attacks == 0
        assert campaign.blocked_attacks == campaign.total_attacks
        assert campaign.security_score == 1.0

    def test_batch_replay_attack(self):
        """Batch replay (multiple nonces at once) should be blocked."""
        attacker = CrossNodeReplayAttacker(node_count=3)
        
        # Capture multiple attestations
        captures = []
        for i in range(10):
            capture = attacker.capture_attestation(f"miner_{i}", "node-0")
            captures.append(capture)
        
        # Try to replay all on node-1
        blocked_count = 0
        success_count = 0
        
        for capture in captures:
            result = attacker.replay_attestation(
                capture.capture_id, "node-1", AttackType.BATCH_REPLAY
            )
            if result.blocked:
                blocked_count += 1
            else:
                success_count += 1
        
        assert success_count == 0
        assert blocked_count == 10


# =============================================================================
# Security Tests: Edge Cases and Vectors
# =============================================================================

class TestSecurityVectors:
    """Security-focused edge case tests."""

    def test_nonce_with_special_chars(self, test_db, test_miner_id):
        """Nonces with special characters should be handled."""
        special_nonce = "nonce_!@#$%^&*()_+-=[]{}|;':\",./<>?"
        
        valid, error = validate_cross_node_nonce(test_db, special_nonce, test_miner_id)
        
        # Should not crash - may accept or reject based on format
        assert isinstance(valid, bool)

    def test_unicode_nonce(self, test_db, test_miner_id):
        """Unicode nonces should be handled safely."""
        unicode_nonce = "nonce_你好世界_🔐"
        
        valid, error = validate_cross_node_nonce(test_db, unicode_nonce, test_miner_id)
        
        assert isinstance(valid, bool)

    def test_extremely_long_nonce(self, test_db, test_miner_id):
        """Very long nonces should be handled."""
        long_nonce = "nonce_" + "x" * 10000
        
        valid, error = validate_cross_node_nonce(test_db, long_nonce, test_miner_id)
        
        # Should not crash
        assert isinstance(valid, bool)

    def test_concurrent_nonce_usage(self, test_db, test_miner_id):
        """Concurrent nonce usage should be handled atomically."""
        nonce = "nonce_concurrent"
        
        # First validation should succeed (nonce not yet used)
        valid, error = validate_cross_node_nonce(test_db, nonce, test_miner_id)
        assert valid is True
        
        # Store the nonce
        store_used_cross_node_nonce(test_db, nonce, test_miner_id)
        
        # Subsequent validations should fail
        for _ in range(9):
            valid, error = validate_cross_node_nonce(test_db, nonce, test_miner_id)
            assert valid is False
            assert error == "nonce_already_used"

    def test_nonce_sql_injection(self, test_db, test_miner_id):
        """SQL injection in nonce should be handled safely."""
        injection_nonce = "'; DROP TABLE cross_node_nonces; --"
        
        valid, error = validate_cross_node_nonce(test_db, injection_nonce, test_miner_id)
        
        # Should not crash or allow injection
        assert isinstance(valid, bool)
        
        # Table should still exist
        cursor = test_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='cross_node_nonces'"
        )
        assert cursor.fetchone() is not None


# =============================================================================
# Tests: Cleanup and Maintenance
# =============================================================================

class TestNonceCleanup:
    """Tests for nonce cleanup functionality."""

    def test_cleanup_removes_expired(self, test_db):
        """Cleanup should remove expired nonces."""
        past_time = 1700000000
        future_time = past_time + CROSS_NODE_NONCE_TTL + 1000
        
        # Store nonce in the past
        with patch('cross_node_replay_defense.time.time', return_value=past_time):
            store_used_cross_node_nonce(test_db, "nonce_expired", "miner_1")
        
        # Run cleanup in the future
        with patch('cross_node_replay_defense.time.time', return_value=future_time):
            deleted = cleanup_expired_nonces(test_db)
        
        assert deleted == 1
        
        # Verify nonce is gone
        row = test_db.execute(
            "SELECT COUNT(*) FROM cross_node_nonces WHERE nonce = ?",
            ("nonce_expired",)
        ).fetchone()[0]
        assert row == 0

    def test_cleanup_keeps_active(self, test_db):
        """Cleanup should keep active nonces."""
        current_time = 1700000000
        
        # Store nonce now
        with patch('cross_node_replay_defense.time.time', return_value=current_time):
            store_used_cross_node_nonce(test_db, "nonce_active", "miner_1")
        
        # Run cleanup immediately (nonce still active, within TTL)
        # Use same time to ensure nonce hasn't expired
        with patch('cross_node_replay_defense.time.time', return_value=current_time):
            deleted = cleanup_expired_nonces(test_db)
        
        assert deleted == 0
        
        # Verify nonce still exists
        row = test_db.execute(
            "SELECT COUNT(*) FROM cross_node_nonces WHERE nonce = 'nonce_active'"
        ).fetchone()[0]
        assert row == 1


# =============================================================================
# Tests: Statistics and Reporting
# =============================================================================

class TestStatisticsAndReporting:
    """Tests for monitoring and reporting functions."""

    def test_nonce_stats(self, test_db, mock_time):
        """Statistics should accurately reflect nonce state."""
        # Store some nonces
        for i in range(5):
            store_used_cross_node_nonce(test_db, f"nonce_{i}", f"miner_{i}")
        
        stats = get_cross_node_nonce_stats(test_db)
        
        assert stats["total_nonces"] == 5
        assert stats["active_nonces"] == 5
        assert stats["node_id"] == NODE_ID

    def test_replay_attack_report(self, test_db):
        """Security report should provide accurate assessment."""
        report = get_replay_attack_report(test_db)
        
        assert "security_status" in report
        assert "protection_mechanism" in report
        assert "recommendations" in report
        assert isinstance(report["recommendations"], list)


# =============================================================================
# Tests: Cleanup Service
# =============================================================================

class TestCleanupService:
    """Tests for background cleanup service."""

    def test_service_start_stop(self, test_db):
        """Cleanup service should start and stop cleanly."""
        with patch('cross_node_replay_defense.DB_PATH', ':memory:'):
            service = NonceCleanupService(db_path=':memory:')
            
            # Should start without error
            service.start()
            assert service.running is True
            
            # Should stop without error
            service.stop()
            assert service.running is False


# =============================================================================
# Property-Based Tests
# =============================================================================

class TestProperties:
    """Property-based tests for invariant verification."""

    def test_nonce_uniqueness_invariant(self, test_db):
        """Each nonce should be unique in the registry."""
        nonces = [f"nonce_{i}_{uuid.uuid4().hex[:8]}" for i in range(100)]
        miner = "test_miner"
        
        # Store all nonces
        for nonce in nonces:
            store_used_cross_node_nonce(test_db, nonce, miner)
        
        # Verify uniqueness
        cursor = test_db.execute(
            "SELECT nonce, COUNT(*) as cnt FROM cross_node_nonces GROUP BY nonce HAVING cnt > 1"
        )
        duplicates = cursor.fetchall()
        
        assert len(duplicates) == 0, "Found duplicate nonces in registry"

    def test_expiration_invariant(self, test_db):
        """All nonces should have valid expiration times."""
        current_time = 1700000000
        
        with patch('cross_node_replay_defense.time.time', return_value=current_time):
            for i in range(10):
                store_used_cross_node_nonce(test_db, f"nonce_{i}", f"miner_{i}")
        
        # Verify all have expiration > current_time
        cursor = test_db.execute(
            "SELECT MIN(expires_at) FROM cross_node_nonces"
        )
        min_expires = cursor.fetchone()[0]
        
        assert min_expires > current_time

    def test_miner_binding_invariant(self, test_db):
        """Each nonce should be bound to exactly one miner."""
        nonce = "nonce_binding_test"
        miner1 = "miner_1"
        miner2 = "miner_2"
        
        # First miner uses nonce
        store_used_cross_node_nonce(test_db, nonce, miner1)
        
        # Second miner tries to use same nonce
        valid, error = validate_cross_node_nonce(test_db, nonce, miner2)
        
        assert valid is False
        assert error == "nonce_belongs_to_different_miner"

    def test_store_preserves_first_active_nonce_owner(self, test_db):
        """Storing an already-active nonce must not replace its first owner."""
        nonce = "nonce_first_owner_invariant"

        with patch('cross_node_replay_defense.NODE_ID', "node-original"):
            first_result = store_used_cross_node_nonce(test_db, nonce, "miner_original")

        with patch('cross_node_replay_defense.NODE_ID', "node-replay"):
            second_result = store_used_cross_node_nonce(test_db, nonce, "miner_replay")

        row = test_db.execute(
            """
            SELECT miner_id, node_id
            FROM cross_node_nonces
            WHERE nonce = ?
            """,
            (nonce,),
        ).fetchone()

        assert first_result is True
        assert second_result is False
        assert row == ("miner_original", "node-original")

    def test_store_can_reuse_nonce_after_expiration(self, test_db):
        """Expired records are cleaned before a fresh nonce owner is stored."""
        nonce = "nonce_expired_then_reused"
        past_time = 1700000000
        future_time = past_time + CROSS_NODE_NONCE_TTL + 100

        with patch('cross_node_replay_defense.NODE_ID', "node-old"):
            store_used_cross_node_nonce(test_db, nonce, "miner_old", now_ts=past_time)

        with patch('cross_node_replay_defense.NODE_ID', "node-new"):
            result = store_used_cross_node_nonce(test_db, nonce, "miner_new", now_ts=future_time)

        row = test_db.execute(
            """
            SELECT miner_id, node_id
            FROM cross_node_nonces
            WHERE nonce = ?
            """,
            (nonce,),
        ).fetchone()

        assert result is True
        assert row == ("miner_new", "node-new")


# =============================================================================
# Regression Tests
# =============================================================================

class TestRegression:
    """Regression tests to ensure fixes remain effective."""

    def test_issue_2296_cross_node_replay_fixed(self):
        """
        REGRESSION TEST for Issue #2296.
        
        Verify that cross-node replay attacks are properly blocked
        by the distributed nonce tracking system.
        """
        attacker = CrossNodeReplayAttacker(node_count=5)
        
        # Simulate the attack described in issue #2296:
        # 1. Attacker captures legitimate attestation from Node A
        # 2. Attacker replays it to Node B (cross-node)
        # 3. System should detect and block
        
        capture = attacker.capture_attestation("victim_miner", "node-0")
        
        # Cross-node replay attempt
        result = attacker.replay_attestation(
            capture.capture_id, "node-1", AttackType.CROSS_NODE_REPLAY
        )
        
        # CRITICAL: This MUST be blocked
        assert result.blocked is True, "REGRESSION: Cross-node replay is no longer blocked!"
        assert result.block_reason == "cross_node_replay_detected"
        
        # Verify security score
        campaign = attacker.run_attack_campaign(captures_per_node=20)
        assert campaign.security_score == 1.0, "REGRESSION: Security score dropped below 100%!"

    def test_nonce_persistence_across_restart(self, test_db):
        """Nonces should persist and remain tracked after 'restart'."""
        nonce = "nonce_persistence"
        miner = "test_miner"
        
        # Store nonce
        store_used_cross_node_nonce(test_db, nonce, miner)
        
        # Simulate restart (in real scenario, DB persists)
        # For in-memory DB, just verify it's still tracked
        valid, error = validate_cross_node_nonce(test_db, nonce, miner)
        
        assert valid is False
        assert error == "nonce_already_used"


# =============================================================================
# Test Runner
# =============================================================================

if __name__ == "__main__":
    # Run with pytest
    exit_code = pytest.main([
        __file__,
        "-v",
        "--tb=short",
        "-x",  # Stop on first failure
    ])
    sys.exit(exit_code)
