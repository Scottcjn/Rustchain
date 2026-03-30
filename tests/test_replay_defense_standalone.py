#!/usr/bin/env python3
"""
Standalone Test Suite for Hardware Fingerprint Replay Attack Defense - Issue #2276
==================================================================================
Tests the replay attack detection and prevention mechanisms for hardware
fingerprint submissions in RustChain.

Run: python3 tests/test_replay_defense_standalone.py -v
"""

import hashlib
import json
import os
import sqlite3
import sys
import time
import tempfile
from pathlib import Path
from typing import Dict, Any

# Set DB path BEFORE any imports
TEST_DB_FD, TEST_DB_PATH = tempfile.mkstemp(suffix='.db', prefix='test_replay_')
os.environ['DB_PATH'] = TEST_DB_PATH
os.environ['RUSTCHAIN_DB_PATH'] = TEST_DB_PATH

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
NODE_PATH = PROJECT_ROOT / "node"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(NODE_PATH))

# Import replay defense module (will use test DB path)
from hardware_fingerprint_replay import (
    init_replay_defense_schema,
    compute_fingerprint_hash,
    compute_entropy_profile_hash,
    check_fingerprint_replay,
    check_entropy_collision,
    check_fingerprint_rate_limit,
    record_fingerprint_submission,
    detect_fingerprint_anomalies,
    get_replay_defense_report,
    REPLAY_WINDOW_SECONDS,
    MAX_FINGERPRINT_SUBMISSIONS_PER_HOUR,
    DB_PATH
)


# ============================================================================
# Test Utilities
# ============================================================================

import pytest

@pytest.fixture(autouse=True)
def setup_teardown():
    """Reset the database for each test."""
    # Use a unique DB for each test to avoid file locking on Windows
    unique_db_path = f"{TEST_DB_PATH}_{os.getpid()}_{time.time_ns()}.db"
    import hardware_fingerprint_replay
    hardware_fingerprint_replay.DB_PATH = unique_db_path
    
    init_replay_defense_schema()
    yield
    
    # Cleanup
    if os.path.exists(unique_db_path):
        for _ in range(5):
            try:
                os.remove(unique_db_path)
                break
            except PermissionError:
                time.sleep(0.1)

def get_valid_fingerprint() -> Dict[str, Any]:
    """Return a valid fingerprint payload for testing."""
    return {
        "checks": {
            "anti_emulation": {
                "passed": True,
                "data": {
                    "vm_indicators": [],
                    "paths_checked": ["/proc/cpuinfo"],
                    "hypervisor_detected": False
                }
            },
            "clock_drift": {
                "passed": True,
                "data": {
                    "cv": 0.05,
                    "samples": 100,
                    "drift_hash": "abc123def456"
                }
            },
            "cache_timing": {
                "passed": True,
                "data": {
                    "cache_hash": "cache789",
                    "L1": 5,
                    "L2": 15,
                    "tone_ratios": [3.0, 2.5, 1.8]
                }
            },
            "thermal_drift": {
                "passed": True,
                "data": {
                    "ratio": 0.15,
                    "thermal_drift_pct": 5.2
                }
            },
            "instruction_jitter": {
                "passed": True,
                "data": {
                    "cv": 0.08,
                    "jitter_map": {
                        "integer": {"stdev": 500},
                        "branch": {"stdev": 800}
                    }
                }
            },
            "simd_identity": {
                "passed": True,
                "data": {
                    "simd_type": "altivec",
                    "int_float_ratio": 1.2
                }
            }
        },
        "timestamp": int(time.time()),
        "all_passed": True,
        "checks_passed": 6,
        "checks_total": 6
    }


# ============================================================================
# Test Classes
# ============================================================================

class TestFingerprintHashComputation:
    """Test fingerprint hash computation for uniqueness and consistency."""
    
    def test_same_fingerprint_same_hash(self):
        """Verify that identical fingerprints produce identical hashes."""
        fp = get_valid_fingerprint()
        hash1 = compute_fingerprint_hash(fp)
        hash2 = compute_fingerprint_hash(fp)
        
        assert hash1 == hash2, "Same fingerprint should produce same hash"
        assert len(hash1) == 64, "Hash should be 64 characters (SHA-256 hex)"
        print("✓ test_same_fingerprint_same_hash")
    
    def test_different_fingerprints_different_hashes(self):
        """Verify that different fingerprints produce different hashes."""
        fp1 = get_valid_fingerprint()
        hash1 = compute_fingerprint_hash(fp1)
        
        # Modify fingerprint slightly
        fp2 = get_valid_fingerprint()
        fp2["checks"]["clock_drift"]["data"]["cv"] = 0.06
        hash2 = compute_fingerprint_hash(fp2)
        
        assert hash1 != hash2, "Different fingerprints should produce different hashes"
        print("✓ test_different_fingerprints_different_hashes")
    
    def test_empty_fingerprint_hash(self):
        """Verify handling of empty/None fingerprints."""
        assert compute_fingerprint_hash(None) == "", "None should return empty string"
        # Empty dict returns a hash of the normalized empty structure
        hash = compute_fingerprint_hash({})
        assert len(hash) == 64, "Empty dict should return a 64-character hash"
        print("✓ test_empty_fingerprint_hash")
    
    def test_hash_ignores_volatile_fields(self):
        """Verify that hash computation ignores volatile fields like samples."""
        fp1 = get_valid_fingerprint()
        fp2 = get_valid_fingerprint()
        
        # Change volatile fields that should be ignored
        fp2["checks"]["clock_drift"]["data"]["samples"] = 999
        fp2["checks"]["clock_drift"]["data"]["mean_ns"] = 12345
        
        hash1 = compute_fingerprint_hash(fp1)
        hash2 = compute_fingerprint_hash(fp2)
        
        assert hash1 == hash2, "Hashes should be same (volatile fields ignored)"
        print("✓ test_hash_ignores_volatile_fields")


class TestEntropyProfileHash:
    """Test entropy profile hash computation."""
    
    def test_entropy_hash_consistency(self):
        """Verify consistent entropy hash computation."""
        fp = get_valid_fingerprint()
        hash1 = compute_entropy_profile_hash(fp)
        hash2 = compute_entropy_profile_hash(fp)
        
        assert hash1 == hash2, "Same entropy profile should produce same hash"
        assert len(hash1) == 64, "Hash should be 64 characters"
        print("✓ test_entropy_hash_consistency")
    
    def test_entropy_hash_different_profiles(self):
        """Verify different entropy profiles produce different hashes."""
        fp1 = get_valid_fingerprint()
        hash1 = compute_entropy_profile_hash(fp1)
        
        # Modify entropy values
        fp2 = get_valid_fingerprint()
        fp2["checks"]["clock_drift"]["data"]["cv"] = 0.50
        hash2 = compute_entropy_profile_hash(fp2)
        
        assert hash1 != hash2, "Different entropy profiles should produce different hashes"
        print("✓ test_entropy_hash_different_profiles")
    
    def test_entropy_hash_empty_fingerprint(self):
        """Verify entropy hash handles empty fingerprints."""
        hash = compute_entropy_profile_hash({})
        assert len(hash) == 64, "Empty fingerprint should produce valid hash"
        print("✓ test_entropy_hash_empty_fingerprint")


class TestFingerprintReplayDetection:
    """Test fingerprint replay attack detection."""
    
    def test_no_replay_first_submission(self):
        """Verify first submission is not flagged as replay."""
        fp = get_valid_fingerprint()
        fp_hash = compute_fingerprint_hash(fp)
        
        is_replay, reason, details = check_fingerprint_replay(
            fingerprint_hash=fp_hash,
            nonce=hashlib.sha256(os.urandom(32)).hexdigest(),
            wallet_address="RTC1234567890abcdef1234567890abcdef12",
            miner_id="test_miner_001"
        )
        
        assert is_replay is False, f"First submission should not be replay: {reason}"
        assert reason == "no_replay_detected"
        print("✓ test_no_replay_first_submission")
    
    def test_replay_same_fingerprint_different_nonce(self):
        """Verify replay is detected when same fingerprint submitted with different nonce."""
        fp = get_valid_fingerprint()
        fp_hash = compute_fingerprint_hash(fp)
        nonce1 = hashlib.sha256(os.urandom(32)).hexdigest()
        test_wallet = "RTC1234567890abcdef1234567890abcdef12"
        test_miner = "test_miner_001"
        
        # Record first submission
        record_fingerprint_submission(
            fingerprint=fp,
            nonce=nonce1,
            wallet_address=test_wallet,
            miner_id=test_miner
        )
        
        # Try replay with different nonce
        replay_nonce = hashlib.sha256(os.urandom(32)).hexdigest()
        is_replay, reason, details = check_fingerprint_replay(
            fingerprint_hash=fp_hash,
            nonce=replay_nonce,
            wallet_address=test_wallet,
            miner_id=test_miner
        )
        
        assert is_replay is True, "Replay should be detected"
        assert reason == "fingerprint_replay_detected", f"Wrong reason: {reason}"
        assert details['attack_type'] == 'exact_fingerprint_replay'
        assert details['severity'] == 'high'
        print("✓ test_replay_same_fingerprint_different_nonce")
    
    def test_replay_same_nonce_different_wallet(self):
        """Verify nonce collision attack is detected."""
        fp = get_valid_fingerprint()
        fp_hash = compute_fingerprint_hash(fp)
        test_nonce = hashlib.sha256(os.urandom(32)).hexdigest()
        test_wallet = "RTC1234567890abcdef1234567890abcdef12"
        test_miner = "test_miner_001"
        
        # Record first submission
        record_fingerprint_submission(
            fingerprint=fp,
            nonce=test_nonce,
            wallet_address=test_wallet,
            miner_id=test_miner
        )
        
        # Try to use same nonce from different wallet
        attacker_wallet = "RTCattacker1234567890abcdef12345678"
        is_replay, reason, details = check_fingerprint_replay(
            fingerprint_hash=fp_hash,
            nonce=test_nonce,
            wallet_address=attacker_wallet,
            miner_id=test_miner
        )
        
        # Should detect replay (same fingerprint, same nonce, different wallet)
        # The first check catches it as fingerprint replay
        assert is_replay is True, "Replay should be detected"
        assert reason in ("fingerprint_replay_detected", "nonce_collision_attack"), f"Wrong reason: {reason}"
        assert details['severity'] in ('high', 'critical')
        print("✓ test_replay_same_nonce_different_wallet")


class TestEntropyCollisionDetection:
    """Test entropy profile collision detection across wallets."""
    
    def test_no_collision_unique_entropy(self):
        """Verify unique entropy profiles don't trigger collision."""
        fp = get_valid_fingerprint()
        entropy_hash = compute_entropy_profile_hash(fp)
        
        is_collision, reason, details = check_entropy_collision(
            entropy_profile_hash=entropy_hash,
            wallet_address="RTC1234567890abcdef1234567890abcdef12",
            miner_id="test_miner_001"
        )
        
        assert is_collision is False, f"Unique entropy should not collide: {reason}"
        assert reason == "no_collision_detected"
        print("✓ test_no_collision_unique_entropy")
    
    def test_collision_same_entropy_different_wallet(self):
        """Verify entropy collision detected when same profile used by different wallet."""
        fp = get_valid_fingerprint()
        entropy_hash = compute_entropy_profile_hash(fp)
        test_wallet = "RTC1234567890abcdef1234567890abcdef12"
        test_miner = "test_miner_001"
        
        # Record submission from first wallet
        record_fingerprint_submission(
            fingerprint=fp,
            nonce=hashlib.sha256(os.urandom(32)).hexdigest(),
            wallet_address=test_wallet,
            miner_id=test_miner
        )
        
        # Check collision from different wallet
        attacker_wallet = "RTCattacker1234567890abcdef12345678"
        is_collision, reason, details = check_entropy_collision(
            entropy_profile_hash=entropy_hash,
            wallet_address=attacker_wallet,
            miner_id="attacker_miner"
        )
        
        assert is_collision is True, "Entropy collision should be detected"
        assert reason == "entropy_profile_collision", f"Wrong reason: {reason}"
        assert details['attack_type'] == 'entropy_sharing'
        assert details['severity'] == 'medium'
        print("✓ test_collision_same_entropy_different_wallet")


class TestFingerprintRateLimiting:
    """Test rate limiting for fingerprint submissions."""
    
    def test_first_submission_allowed(self):
        """Verify first submission from hardware is allowed."""
        hw_id = "hw_test_001"
        wallet = "RTC1234567890abcdef1234567890abcdef12"
        
        is_allowed, reason, details = check_fingerprint_rate_limit(
            hardware_id=hw_id,
            wallet_address=wallet
        )
        
        assert is_allowed is True, f"First submission should be allowed: {reason}"
        assert reason == "first_submission"
        print("✓ test_first_submission_allowed")
    
    def test_rate_limit_exceeded(self):
        """Verify rate limiting blocks excessive submissions."""
        hw_id = "hw_test_ratelimit"
        wallet = "RTC1234567890abcdef1234567890abcdef12"
        
        # Submit MAX_FINGERPRINT_SUBMISSIONS_PER_HOUR times
        for i in range(MAX_FINGERPRINT_SUBMISSIONS_PER_HOUR):
            is_allowed, reason, _ = check_fingerprint_rate_limit(
                hardware_id=hw_id,
                wallet_address=wallet
            )
            assert is_allowed is True, f"Submission {i+1} should be allowed"
        
        # Next submission should be blocked
        is_allowed, reason, details = check_fingerprint_rate_limit(
            hardware_id=hw_id,
            wallet_address=wallet
        )
        
        assert is_allowed is False, "Rate limit should block excessive submissions"
        assert reason == "rate_limit_exceeded", f"Wrong reason: {reason}"
        assert details['limit'] == MAX_FINGERPRINT_SUBMISSIONS_PER_HOUR
        print("✓ test_rate_limit_exceeded")


class TestIntegrationScenarios:
    """Integration tests for complete replay attack scenarios."""
    
    def test_scenario_replay_attack_blocked(self):
        """Integration test: Complete replay attack is blocked."""
        # Step 1: Legitimate miner submits fingerprint
        fp = get_valid_fingerprint()
        fp_hash = compute_fingerprint_hash(fp)
        nonce1 = hashlib.sha256(os.urandom(32)).hexdigest()
        test_wallet = "RTC1234567890abcdef1234567890abcdef12"
        test_miner = "test_miner_legit"
        
        record_fingerprint_submission(
            fingerprint=fp,
            nonce=nonce1,
            wallet_address=test_wallet,
            miner_id=test_miner
        )
        
        # Step 2: Attacker captures fingerprint and tries to replay
        attacker_wallet = "RTCattacker1234567890abcdef12345678"
        nonce2 = hashlib.sha256(os.urandom(32)).hexdigest()
        
        is_replay, reason, details = check_fingerprint_replay(
            fingerprint_hash=fp_hash,
            nonce=nonce2,
            wallet_address=attacker_wallet,
            miner_id=test_miner
        )
        
        # Verify attack is blocked
        assert is_replay is True, "Replay attack should be detected"
        assert reason == "fingerprint_replay_detected"
        assert details['attack_type'] == 'exact_fingerprint_replay'
        print("✓ test_scenario_replay_attack_blocked")
    
    def test_scenario_entropy_theft_blocked(self):
        """Integration test: Entropy profile theft is blocked."""
        fp = get_valid_fingerprint()
        entropy_hash = compute_entropy_profile_hash(fp)
        test_wallet = "RTC1234567890abcdef1234567890abcdef12"
        test_miner = "test_miner_entropy"
        
        # Step 1: Legitimate miner registers with entropy profile
        record_fingerprint_submission(
            fingerprint=fp,
            nonce=hashlib.sha256(os.urandom(32)).hexdigest(),
            wallet_address=test_wallet,
            miner_id=test_miner
        )
        
        # Step 2: Attacker tries to use same entropy profile
        attacker_wallet = "RTCattacker1234567890abcdef12345678"
        
        is_collision, reason, details = check_entropy_collision(
            entropy_profile_hash=entropy_hash,
            wallet_address=attacker_wallet,
            miner_id="attacker_miner"
        )
        
        # Verify theft is detected
        assert is_collision is True, "Entropy theft should be detected"
        assert reason == "entropy_profile_collision"
        print("✓ test_scenario_entropy_theft_blocked")


# ============================================================================
# Standalone DB helpers (used by run_tests(), not by pytest)
# ============================================================================

def setup_test_db():
    """Initialise the replay-defense schema on the standalone TEST_DB_PATH."""
    import hardware_fingerprint_replay
    hardware_fingerprint_replay.DB_PATH = TEST_DB_PATH
    init_replay_defense_schema()


def cleanup_test_db():
    """Remove the temporary test database created by setup_test_db()."""
    for path in (TEST_DB_PATH,):
        if os.path.exists(path):
            for _ in range(5):
                try:
                    os.remove(path)
                    break
                except PermissionError:
                    time.sleep(0.1)


# ============================================================================
# Test Runner
# ============================================================================

def run_tests():
    """Run all tests and report results."""
    print("=" * 70)
    print("Hardware Fingerprint Replay Attack Defense - Test Suite #2276")
    print("=" * 70)
    print(f"Test DB: {TEST_DB_PATH}")
    print(f"Replay Window: {REPLAY_WINDOW_SECONDS}s")
    print(f"Rate Limit: {MAX_FINGERPRINT_SUBMISSIONS_PER_HOUR}/hour")
    print("=" * 70)
    
    # Initialize test DB
    setup_test_db()
    
    test_classes = [
        TestFingerprintHashComputation,
        TestEntropyProfileHash,
        TestFingerprintReplayDetection,
        TestEntropyCollisionDetection,
        TestFingerprintRateLimiting,
        TestIntegrationScenarios,
    ]
    
    total_tests = 0
    passed_tests = 0
    failed_tests = []
    
    for test_class in test_classes:
        print(f"\n{test_class.__name__}:")
        instance = test_class()
        
        for method_name in dir(instance):
            if method_name.startswith('test_'):
                total_tests += 1
                try:
                    method = getattr(instance, method_name)
                    method()
                    passed_tests += 1
                except AssertionError as e:
                    failed_tests.append((f"{test_class.__name__}.{method_name}", str(e)))
                    print(f"✗ {method_name}: {e}")
                except Exception as e:
                    failed_tests.append((f"{test_class.__name__}.{method_name}", str(e)))
                    print(f"✗ {method_name}: ERROR - {e}")
    
    # Summary
    print("\n" + "=" * 70)
    print(f"RESULTS: {passed_tests}/{total_tests} tests passed")
    
    if failed_tests:
        print(f"\nFAILED TESTS ({len(failed_tests)}):")
        for test_name, error in failed_tests:
            print(f"  - {test_name}: {error}")
    else:
        print("✓ ALL TESTS PASSED!")
    
    print("=" * 70)
    
    # Cleanup
    cleanup_test_db()
    
    return len(failed_tests) == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
