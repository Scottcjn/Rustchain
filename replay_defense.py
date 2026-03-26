#!/usr/bin/env python3
"""
Replay Defense Module - Issue #2276
===================================
Hardware Fingerprint Replay Attack Defense for RustChain Proof of Antiquity.

This module provides the main entry point for replay attack defense, wrapping
the implementation in node/hardware_fingerprint_replay.py for easier importing
and integration.

Bounty Requirements:
1. Replayed fingerprint must be rejected
2. Fresh fingerprint must be accepted  
3. Modified replay (changed nonce but old data) must be rejected

Integration Point:
  The /attest/submit endpoint calls these functions BEFORE fingerprint validation.
  See: node/rustchain_v2_integrated_v2.2.1_rip200.py lines 2702-2780

Usage:
  from replay_defense import (
      check_replay_attack,
      record_submission,
      ReplayDefenseResult
  )
  
  # Check if submission is a replay attack
  result = check_replay_attack(fingerprint, nonce, wallet, miner)
  if result.is_replay:
      return jsonify({"error": "replay_detected"}), 409
  
  # Record successful submission
  record_submission(fingerprint, nonce, wallet, miner)

Files:
  - replay_defense.py: This wrapper module (main entry point)
  - node/hardware_fingerprint_replay.py: Core implementation
  - replay_attack_poc.py: Proof of concept demonstrating attacks
  - tests/test_replay_bounty.py: Bounty requirement tests

Author: RustChain Security Team
Issue: #2276
Date: 2026-03-22
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any, Tuple, Optional, NamedTuple
from dataclasses import dataclass

# Add node directory to path for importing core implementation
PROJECT_ROOT = Path(__file__).resolve().parent
NODE_PATH = PROJECT_ROOT / "node"
sys.path.insert(0, str(NODE_PATH))

# Import core implementation
try:
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
        ENTROPY_HASH_COLLISION_TOLERANCE,
        DB_PATH
    )
    HAVE_REPLAY_DEFENSE = True
except ImportError as e:
    HAVE_REPLAY_DEFENSE = False
    print(f"[REPLAY_DEFENSE] Warning: Core module not available: {e}")


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class ReplayDefenseResult:
    """Result of a replay defense check."""
    is_replay: bool
    """True if replay attack detected."""
    
    reason: str
    """Reason code for the result."""
    
    allowed: bool
    """True if submission should be allowed."""
    
    details: Optional[Dict[str, Any]] = None
    """Additional details about the detection."""
    
    http_status: int = 200
    """Recommended HTTP status code for response."""
    
    @classmethod
    def allowed_result(cls, reason: str = "ok") -> 'ReplayDefenseResult':
        """Create an 'allowed' result."""
        return cls(is_replay=False, reason=reason, allowed=True, http_status=200)
    
    @classmethod
    def replay_detected(cls, reason: str, details: Dict[str, Any] = None) -> 'ReplayDefenseResult':
        """Create a 'replay detected' result."""
        return cls(
            is_replay=True, 
            reason=reason, 
            allowed=False, 
            details=details,
            http_status=409
        )
    
    @classmethod
    def rate_limited(cls, details: Dict[str, Any] = None) -> 'ReplayDefenseResult':
        """Create a 'rate limited' result."""
        return cls(
            is_replay=False,
            reason="rate_limit_exceeded",
            allowed=False,
            details=details,
            http_status=429
        )


# ============================================================================
# Main API Functions
# ============================================================================

def check_replay_attack(
    fingerprint: Dict[str, Any],
    nonce: str,
    wallet_address: str,
    miner_id: str,
    check_entropy: bool = True,
    check_rate_limit: bool = True
) -> ReplayDefenseResult:
    """
    Check if a fingerprint submission is a replay attack.
    
    This is the main entry point for replay defense, called by /attest/submit
    BEFORE fingerprint validation.
    
    Args:
        fingerprint: The hardware fingerprint dictionary
        nonce: The attestation nonce (should be unique per submission)
        wallet_address: The wallet address submitting the attestation
        miner_id: The miner identifier
        check_entropy: Whether to check entropy collision
        check_rate_limit: Whether to check rate limiting
    
    Returns:
        ReplayDefenseResult with is_replay, reason, and details
    
    Integration Point:
        Called from node/rustchain_v2_integrated_v2.2.1_rip200.py
        at line ~2702 in the /attest/submit endpoint.
    
    Example:
        result = check_replay_attack(fp, nonce, wallet, miner)
        if not result.allowed:
            return jsonify({
                "ok": False,
                "error": result.reason,
                "details": result.details
            }), result.http_status
    """
    if not HAVE_REPLAY_DEFENSE:
        return ReplayDefenseResult.allowed_result("replay_defense_unavailable")
    
    # Compute fingerprint hash
    fp_hash = compute_fingerprint_hash(fingerprint)
    
    # Check 1: Fingerprint replay detection
    is_replay, reason, details = check_fingerprint_replay(
        fingerprint_hash=fp_hash,
        nonce=nonce,
        wallet_address=wallet_address,
        miner_id=miner_id
    )
    
    if is_replay:
        return ReplayDefenseResult.replay_detected(reason, details)
    
    # Check 2: Entropy collision detection (optional)
    if check_entropy:
        entropy_hash = compute_entropy_profile_hash(fingerprint)
        is_collision, coll_reason, coll_details = check_entropy_collision(
            entropy_profile_hash=entropy_hash,
            wallet_address=wallet_address,
            miner_id=miner_id
        )
        
        if is_collision:
            return ReplayDefenseResult.replay_detected(coll_reason, coll_details)
    
    # Check 3: Rate limiting (optional)
    if check_rate_limit:
        # Compute hardware ID if available
        hw_id = _compute_hardware_id(fingerprint)
        
        rate_ok, rate_reason, rate_details = check_fingerprint_rate_limit(
            hardware_id=hw_id,
            wallet_address=wallet_address
        )
        
        if not rate_ok:
            return ReplayDefenseResult.rate_limited(rate_details)
    
    # All checks passed
    return ReplayDefenseResult.allowed_result("ok")


def record_submission(
    fingerprint: Dict[str, Any],
    nonce: str,
    wallet_address: str,
    miner_id: str,
    hardware_id: Optional[str] = None,
    attestation_valid: bool = True
) -> Dict[str, Any]:
    """
    Record a fingerprint submission for future replay detection.
    
    Call this AFTER a successful attestation to track the submission
    for future replay detection.
    
    Args:
        fingerprint: The hardware fingerprint dictionary
        nonce: The attestation nonce used
        wallet_address: The wallet that submitted
        miner_id: The miner identifier
        hardware_id: Optional hardware binding ID
        attestation_valid: Whether the attestation passed validation
    
    Returns:
        Dict with submission details (hash, sequence number, etc.)
    
    Integration Point:
        Called from node/rustchain_v2_integrated_v2.2.1_rip200.py
        at line ~2762 after successful attestation.
    """
    if not HAVE_REPLAY_DEFENSE:
        return {"recorded": False, "reason": "replay_defense_unavailable"}
    
    result = record_fingerprint_submission(
        fingerprint=fingerprint,
        nonce=nonce,
        wallet_address=wallet_address,
        miner_id=miner_id,
        hardware_id=hardware_id,
        attestation_valid=attestation_valid
    )
    result["recorded"] = True
    return result


def get_fingerprint_hash(fingerprint: Dict[str, Any]) -> str:
    """
    Compute the cryptographic hash of a fingerprint.
    
    Args:
        fingerprint: The fingerprint dictionary
    
    Returns:
        SHA-256 hash (hex) of the normalized fingerprint
    """
    if not HAVE_REPLAY_DEFENSE:
        return ""
    return compute_fingerprint_hash(fingerprint)


def get_entropy_hash(fingerprint: Dict[str, Any]) -> str:
    """
    Compute the entropy profile hash of a fingerprint.
    
    Args:
        fingerprint: The fingerprint dictionary
    
    Returns:
        SHA-256 hash (hex) of the entropy profile
    """
    if not HAVE_REPLAY_DEFENSE:
        return ""
    return compute_entropy_profile_hash(fingerprint)


def check_anomalies(
    miner_id: str,
    wallet_address: str,
    fingerprint: Dict[str, Any]
) -> Tuple[bool, list]:
    """
    Check for anomalous fingerprint patterns.
    
    This is a logging-only check that doesn't block submissions.
    
    Args:
        miner_id: The miner identifier
        wallet_address: The wallet address
        fingerprint: The fingerprint dictionary
    
    Returns:
        Tuple of (has_anomalies, list of anomaly details)
    """
    if not HAVE_REPLAY_DEFENSE:
        return False, []
    
    fp_hash = compute_fingerprint_hash(fingerprint)
    return detect_fingerprint_anomalies(miner_id, wallet_address, fp_hash)


def get_report(
    wallet_address: Optional[str] = None,
    miner_id: Optional[str] = None,
    hours: int = 24
) -> Dict[str, Any]:
    """
    Generate a replay defense monitoring report.
    
    Args:
        wallet_address: Optional wallet to filter by
        miner_id: Optional miner to filter by
        hours: Time window in hours
    
    Returns:
        Dict with replay defense statistics
    """
    if not HAVE_REPLAY_DEFENSE:
        return {"available": False}
    
    report = get_replay_defense_report(wallet_address, miner_id, hours)
    report["available"] = True
    return report


def initialize() -> bool:
    """
    Initialize the replay defense database schema.
    
    Call this on application startup.
    
    Returns:
        True if initialization succeeded
    """
    if not HAVE_REPLAY_DEFENSE:
        return False
    
    try:
        init_replay_defense_schema()
        return True
    except Exception as e:
        print(f"[REPLAY_DEFENSE] Initialization error: {e}")
        return False


# ============================================================================
# Helper Functions
# ============================================================================

def _compute_hardware_id(fingerprint: Dict[str, Any]) -> Optional[str]:
    """
    Compute a hardware ID from fingerprint data for rate limiting.
    
    This is a simplified version - the full implementation is in
    rustchain_v2_integrated_v2.2.1_rip200.py.
    """
    if not fingerprint or not isinstance(fingerprint, dict):
        return None
    
    checks = fingerprint.get('checks', {})
    
    # Use cache hash as hardware identifier
    cache_data = checks.get('cache_timing', {}).get('data', {})
    if isinstance(cache_data, dict) and cache_data.get('cache_hash'):
        return f"hw_{cache_data['cache_hash']}"
    
    # Fallback to entropy hash
    entropy_hash = compute_entropy_profile_hash(fingerprint)
    if entropy_hash:
        return f"hw_{entropy_hash[:16]}"
    
    return None


# ============================================================================
# Module Initialization
# ============================================================================

# Initialize on import
if HAVE_REPLAY_DEFENSE:
    try:
        initialize()
    except Exception as e:
        print(f"[REPLAY_DEFENSE] Init warning: {e}")


# ============================================================================
# CLI Entry Point
# ============================================================================

if __name__ == "__main__":
    print("Replay Defense Module - Issue #2276")
    print("=" * 50)
    print(f"Status: {'Available' if HAVE_REPLAY_DEFENSE else 'Not Available'}")
    
    if HAVE_REPLAY_DEFENSE:
        print(f"Database: {DB_PATH}")
        print(f"Replay Window: {REPLAY_WINDOW_SECONDS}s")
        print(f"Rate Limit: {MAX_FINGERPRINT_SUBMISSIONS_PER_HOUR}/hour")
        print(f"Collision Tolerance: {ENTROPY_HASH_COLLISION_TOLERANCE:.0%}")
    
    print("\nUsage:")
    print("  from replay_defense import check_replay_attack, record_submission")
    print("  ")
    print("  result = check_replay_attack(fingerprint, nonce, wallet, miner)")
    print("  if not result.allowed:")
    print("      return error_response(result)")
    print("  record_submission(fingerprint, nonce, wallet, miner)")
    
    # Run POC if requested
    if len(sys.argv) > 1 and sys.argv[1] in ('--test', '--poc', '-t'):
        print("\nRunning proof of concept...")
        import replay_attack_poc
        replay_attack_poc.run_all_scenarios()
