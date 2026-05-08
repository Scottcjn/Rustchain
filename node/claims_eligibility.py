#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
RIP-305 Track D: Claims Eligibility Verification
================================================

Provides eligibility verification for reward claims with comprehensive validation:
- Attestation status within TTL window
- Epoch participation verification
- Hardware fingerprint validation
- Fleet detection integration (RIP-0201)
- Wallet registration check
- Duplicate claim prevention

Usage:
    from claims_eligibility import check_claim_eligibility
    
    result = check_claim_eligibility(
        db_path="/path/to/node.db",
        miner_id="n64-scott-unit1",
        epoch=1234,
        current_slot=175680,
        current_ts=1741564800
    )
"""

import sqlite3
import time
from typing import Dict, Optional, Tuple, Any
from datetime import datetime

# Import RIP-200 modules for compatibility
try:
    from rip_200_round_robin_1cpu1vote import (
        get_attested_miners,
        get_time_aged_multiplier,
        get_chain_age_years,
        ANTIQUITY_MULTIPLIERS,
        ATTESTATION_TTL,
        BLOCK_TIME,
        GENESIS_TIMESTAMP
    )
except ImportError:
    # Fallback defaults if running standalone
    ATTESTATION_TTL = 86400  # 24 hours
    BLOCK_TIME = 600  # 10 minutes
    GENESIS_TIMESTAMP = 1764706927

# Import RIP-0201 fleet detection
try:
    from fleet_immune_system import get_fleet_status_for_miner
    HAVE_FLEET_IMMUNE = True
except ImportError:
    HAVE_FLEET_IMMUNE = False
    def get_fleet_status_for_miner(db_path: str, miner_id: str, current_ts: int) -> Dict:
        """Mock fleet status when RIP-0201 not available"""
        return {
            "bucket": "unknown",
            "fleet_size": 1,
            "penalty_applied": False,
            "fleet_flagged": False
        }

# Import rewards module
try:
    from rewards_implementation_rip200 import PER_EPOCH_URTC
except ImportError:
    PER_EPOCH_URTC = 150_000_000  # 1.5 RTC in uRTC (default)


class ClaimsEligibilityError(Exception):
    """Base exception for claims eligibility errors"""
    pass


class MinerNotAttestedError(ClaimsEligibilityError):
    """Miner has no valid attestation within TTL"""
    pass


class NoEpochParticipationError(ClaimsEligibilityError):
    """Miner was not attested during the specified epoch"""
    pass


class FingerprintFailedError(ClaimsEligibilityError):
    """Hardware fingerprint validation failed"""
    pass


class WalletNotRegisteredError(ClaimsEligibilityError):
    """No wallet address registered for this miner"""
    pass


class PendingClaimExistsError(ClaimsEligibilityError):
    """Unprocessed claim already exists for this epoch"""
    pass


class EpochNotSettledError(ClaimsEligibilityError):
    """Epoch has not been settled yet"""
    pass


def validate_miner_id_format(miner_id: str) -> bool:
    """
    Validate miner ID format
    
    Valid miner IDs:
    - Non-empty string
    - Max 128 characters
    - Alphanumeric, hyphens, underscores only
    """
    if not miner_id or not isinstance(miner_id, str):
        return False
    if len(miner_id) > 128:
        return False
    import re
    return bool(re.match(r'^[a-zA-Z0-9_-]+$', miner_id))


def get_miner_attestation(
    db_path: str,
    miner_id: str,
    current_ts: int
) -> Optional[Dict[str, Any]]:
    """
    Get miner's most recent attestation
    
    Returns:
        Dict with attestation details or None if not found/expired
    """
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    miner,
                    device_arch,
                    ts_ok,
                    fingerprint_passed,
                    entropy_score,
                    warthog_bonus
                FROM miner_attest_recent
                WHERE miner = ?
                AND ts_ok >= ?
                ORDER BY ts_ok DESC
                LIMIT 1
            """, (miner_id, current_ts - ATTESTATION_TTL))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            return {
                "miner_id": row["miner"],
                "device_arch": row["device_arch"],
                "last_seen_ts": row["ts_ok"],
                "fingerprint_passed": row["fingerprint_passed"] if "fingerprint_passed" in row.keys() else 1,
                "entropy_score": row["entropy_score"] if "entropy_score" in row.keys() else 0.0,
                "warthog_bonus": row["warthog_bonus"] if "warthog_bonus" in row.keys() else 1.0
            }
    except sqlite3.Error as e:
        print("[CLAIMS] Database error getting attestation")
        return None


def check_epoch_participation(
    db_path: str,
    miner_id: str,
    epoch: int
) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """
    Check if miner was attested during the specified epoch
    
    Returns:
        (participated: bool, epoch_data: dict or None)
    """
    epoch_start_slot = epoch * 144
    epoch_end_slot = epoch_start_slot + 143
    epoch_start_ts = GENESIS_TIMESTAMP + (epoch_start_slot * BLOCK_TIME)
    epoch_end_ts = GENESIS_TIMESTAMP + (epoch_end_slot * BLOCK_TIME)
    
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get any attestation during epoch window (with TTL consideration)
            cursor.execute("""
                SELECT 
                    miner,
                    device_arch,
                    ts_ok,
                    fingerprint_passed,
                    entropy_score
                FROM miner_attest_recent
                WHERE miner = ?
                AND ts_ok >= ?
                AND ts_ok <= ?
                ORDER BY ts_ok DESC
                LIMIT 1
            """, (
                miner_id,
                epoch_start_ts - ATTESTATION_TTL,
                epoch_end_ts
            ))
            
            row = cursor.fetchone()
            if not row:
                return False, None
            
            return True, {
                "epoch": epoch,
                "attestation_ts": row["ts_ok"],
                "device_arch": row["device_arch"],
                "fingerprint_passed": row["fingerprint_passed"] if "fingerprint_passed" in row.keys() else 1,
                "entropy_score": row["entropy_score"] if "entropy_score" in row.keys() else 0.0
            }
    except sqlite3.Error as e:
        print("[CLAIMS] Database error checking epoch participation")
        return False, None


def get_wallet_address(
    db_path: str,
    miner_id: str
) -> Optional[str]:
    """
    Get registered wallet address for miner
    
    Returns:
        Wallet address string or None if not registered
    """
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # Try miner_wallets table first
            try:
                cursor.execute("""
                    SELECT wallet_address
                    FROM miner_wallets
                    WHERE miner_id = ?
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (miner_id,))
                
                row = cursor.fetchone()
                if row:
                    return row[0]
            except sqlite3.OperationalError:
                # Table doesn't exist, try miner_attest_recent
                pass
            
            # Fallback: check miner_attest_recent for wallet_address column
            cursor.execute("""
                SELECT wallet_address
                FROM miner_attest_recent
                WHERE miner = ?
                AND wallet_address IS NOT NULL
                AND wallet_address != ''
                ORDER BY ts_ok DESC
                LIMIT 1
            """, (miner_id,))
            
            row = cursor.fetchone()
            if row and row[0]:
                return row[0]
            
            return None
    except sqlite3.Error as e:
        print(f"[CLAIMS] Database error getting wallet: {e}")
        return None


def check_pending_claim(
    db_path: str,
    miner_id: str,
    epoch: int
) -> bool:
    """
    Check if there's an existing unprocessed claim for this miner/epoch
    
    Returns:
        True if pending claim exists, False otherwise
    """
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT claim_id
                FROM claims
                WHERE miner_id = ?
                AND epoch = ?
                AND status IN ('pending', 'verifying', 'approved')
                LIMIT 1
            """, (miner_id, epoch))
            
            row = cursor.fetchone()
            return row is not None
    except sqlite3.OperationalError:
        # Claims table doesn't exist yet
        return False
    except sqlite3.Error as e:
        print(f"[CLAIMS] Database error checking pending claims: {e}")
        return False


def is_epoch_settled(
    db_path: str,
    epoch: int,
    current_slot: int
) -> bool:
    """
    Check if epoch has been settled
    
    Epochs are typically settled within 1-2 epochs after completion.
    For simplicity, we consider an epoch settled if we're at least 2 epochs past it.
    """
    settled_epoch = max(0, current_slot // 144 - 2)
    return epoch <= settled_epoch


def calculate_epoch_reward(
    db_path: str,
    miner_id: str,
    epoch: int,
    current_slot: int
) -> int:
    """
    Calculate the reward amount for a miner in a specific epoch
    
    This integrates with RIP-0200 reward calculation logic.
    """
    try:
        from rewards_implementation_rip200 import calculate_epoch_rewards_time_aged
        
        # Get current timestamp from slot
        current_ts = GENESIS_TIMESTAMP + (current_slot * BLOCK_TIME)
        
        # Calculate rewards for the epoch
        rewards = calculate_epoch_rewards_time_aged(
            db_path=db_path,
            epoch=epoch,
            total_reward_urtc=PER_EPOCH_URTC,
            current_slot=current_slot
        )
        
        return rewards.get(miner_id, 0)
    except Exception as e:
        print(f"[CLAIMS] Error calculating reward: {e}")
        # Fallback: return standard per-miner share
        try:
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                
                epoch_start_slot = epoch * 144
                epoch_start_ts = GENESIS_TIMESTAMP + (epoch_start_slot * BLOCK_TIME)
                
                cursor.execute("""
                    SELECT COUNT(DISTINCT miner)
                    FROM miner_attest_recent
                    WHERE ts_ok >= ?
                """, (epoch_start_ts - ATTESTATION_TTL,))
                
                miner_count = cursor.fetchone()[0] or 1
                
                # Equal share as fallback
                return PER_EPOCH_URTC // max(1, miner_count)
        except Exception:
            return 0


def check_claim_eligibility(
    db_path: str,
    miner_id: str,
    epoch: int,
    current_slot: int,
    current_ts: int,
    detailed: bool = True
) -> Dict[str, Any]:
    """
    Comprehensive eligibility check for reward claim
    
    Args:
        db_path: Path to node SQLite database
        miner_id: Unique miner identifier
        epoch: Epoch number to claim rewards for
        current_slot: Current blockchain slot number
        current_ts: Current Unix timestamp
        detailed: If True, include detailed check results
    
    Returns:
        Dict with eligibility result and supporting information:
        {
            "eligible": bool,
            "miner_id": str,
            "epoch": int,
            "reward_urtc": int,
            "reward_rtc": float,
            "wallet_address": str or None,
            "attestation": dict or None,
            "fingerprint": dict or None,
            "fleet_status": dict or None,
            "checks": {
                "attestation_valid": bool,
                "epoch_participation": bool,
                "fingerprint_passed": bool,
                "wallet_registered": bool,
                "no_pending_claim": bool,
                "epoch_settled": bool
            },
            "reason": str or None
        }
    """
    result = {
        "eligible": False,
        "miner_id": miner_id,
        "epoch": epoch,
        "reward_urtc": 0,
        "reward_rtc": 0.0,
        "wallet_address": None,
        "attestation": None,
        "fingerprint": None,
        "fleet_status": None,
        "checks": {
            "attestation_valid": False,
            "epoch_participation": False,
            "fingerprint_passed": False,
            "wallet_registered": False,
            "no_pending_claim": True,
            "epoch_settled": False
        },
        "reason": None
    }
    
    # Validate miner ID format
    if not validate_miner_id_format(miner_id):
        result["reason"] = "invalid_miner_id"
        return result
    
    # Check epoch is settled
    if not is_epoch_settled(db_path, epoch, current_slot):
        result["checks"]["epoch_settled"] = False
        result["reason"] = "epoch_not_settled"
        return result
    result["checks"]["epoch_settled"] = True
    
    # Check current attestation
    attestation = get_miner_attestation(db_path, miner_id, current_ts)
    if not attestation:
        result["checks"]["attestation_valid"] = False
        result["reason"] = "not_attested"
        return result
    
    result["attestation"] = {
        "last_seen_slot": (attestation["last_seen_ts"] - GENESIS_TIMESTAMP) // BLOCK_TIME,
        "last_seen_ts": attestation["last_seen_ts"],
        "device_arch": attestation["device_arch"],
        "antiquity_multiplier": get_time_aged_multiplier(
            attestation["device_arch"],
            get_chain_age_years(current_slot)
        )
    }
    result["checks"]["attestation_valid"] = True
    
    # Check epoch participation
    participated, epoch_data = check_epoch_participation(db_path, miner_id, epoch)
    if not participated:
        result["checks"]["epoch_participation"] = False
        result["reason"] = "no_epoch_participation"
        return result
    
    result["checks"]["epoch_participation"] = True
    
    # Check fingerprint
    fingerprint_passed = epoch_data.get("fingerprint_passed", 1) == 1
    result["fingerprint"] = {
        "passed": fingerprint_passed,
        "entropy_score": epoch_data.get("entropy_score", 0.0)
    }
    
    if not fingerprint_passed:
        result["checks"]["fingerprint_passed"] = False
        result["reason"] = "fingerprint_failed"
        return result
    
    result["checks"]["fingerprint_passed"] = True
    
    # Check wallet registration
    wallet_address = get_wallet_address(db_path, miner_id)
    result["wallet_address"] = wallet_address
    
    if not wallet_address:
        result["checks"]["wallet_registered"] = False
        result["reason"] = "wallet_not_registered"
        return result
    
    result["checks"]["wallet_registered"] = True
    
    # Check for pending claims
    if check_pending_claim(db_path, miner_id, epoch):
        result["checks"]["no_pending_claim"] = False
        result["reason"] = "pending_claim_exists"
        return result
    
    # Get fleet status (RIP-0201)
    if HAVE_FLEET_IMMUNE:
        fleet_status = get_fleet_status_for_miner(db_path, miner_id, current_ts)
        result["fleet_status"] = fleet_status
        
        # Check for fleet penalties
        if fleet_status.get("penalty_applied") or fleet_status.get("fleet_flagged"):
            result["reason"] = "fleet_penalty"
            result["checks"]["fingerprint_passed"] = False
            return result
    else:
        result["fleet_status"] = {
            "bucket": "unknown",
            "fleet_size": 1,
            "penalty_applied": False
        }
    
    # Calculate reward amount
    reward_urtc = calculate_epoch_reward(db_path, miner_id, epoch, current_slot)
    result["reward_urtc"] = reward_urtc
    result["reward_rtc"] = reward_urtc / 100_000_000
    
    # All checks passed
    result["eligible"] = True
    result["reason"] = None
    
    return result


def get_eligible_epochs(
    db_path: str,
    miner_id: str,
    current_slot: int,
    current_ts: int,
    limit: int = 10
) -> Dict[str, Any]:
    """
    Get list of epochs that a miner is eligible to claim
    
    Returns:
        {
            "miner_id": str,
            "epochs": [
                {
                    "epoch": int,
                    "reward_urtc": int,
                    "reward_rtc": float,
                    "claimed": bool,
                    "settled": bool
                }
            ],
            "total_unclaimed_urtc": int,
            "total_unclaimed_rtc": float
        }
    """
    # Get miner's attestation history
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # Get all epochs where miner has attestation
            cursor.execute("""
                SELECT DISTINCT 
                    CAST((ts_ok - ?) / (? * ?) AS INTEGER) as epoch
                FROM miner_attest_recent
                WHERE miner = ?
                AND ts_ok >= ?
                ORDER BY epoch DESC
                LIMIT ?
            """, (
                GENESIS_TIMESTAMP,
                BLOCK_TIME,
                144,  # slots per epoch
                miner_id,
                current_ts - (limit * 144 * BLOCK_TIME),
                limit
            ))
            
            epochs = [row[0] for row in cursor.fetchall() if row[0] >= 0]
    except sqlite3.Error as e:
        print(f"[CLAIMS] Error getting eligible epochs: {e}")
        return {
            "miner_id": miner_id,
            "epochs": [],
            "total_unclaimed_urtc": 0,
            "total_unclaimed_rtc": 0.0
        }
    
    # Check each epoch for eligibility and claim status
    eligible_epochs = []
    total_unclaimed = 0
    
    for epoch in epochs:
        eligibility = check_claim_eligibility(
            db_path=db_path,
            miner_id=miner_id,
            epoch=epoch,
            current_slot=current_slot,
            current_ts=current_ts,
            detailed=False
        )
        
        claimed = not eligibility["checks"]["no_pending_claim"] or \
                  (eligibility["checks"]["no_pending_claim"] and not eligibility["eligible"])
        
        # Check if already claimed (status = settled)
        try:
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT claim_id FROM claims
                    WHERE miner_id = ? AND epoch = ? AND status = 'settled'
                """, (miner_id, epoch))
                if cursor.fetchone():
                    claimed = True
        except sqlite3.OperationalError:
            pass
        
        epoch_info = {
            "epoch": epoch,
            "reward_urtc": eligibility["reward_urtc"],
            "reward_rtc": eligibility["reward_rtc"],
            "claimed": claimed,
            "settled": eligibility["checks"]["epoch_settled"]
        }
        
        eligible_epochs.append(epoch_info)
        
        if not claimed and eligibility["eligible"]:
            total_unclaimed += eligibility["reward_urtc"]
    
    return {
        "miner_id": miner_id,
        "epochs": eligible_epochs,
        "total_unclaimed_urtc": total_unclaimed,
        "total_unclaimed_rtc": total_unclaimed / 100_000_000
    }


# Example usage and testing
if __name__ == "__main__":
    import sys
    
    # Test with mock data
    print("=== RIP-305 Claims Eligibility Test ===\n")
    
    # Create test database
    test_db = ":memory:"
    
    with sqlite3.connect(test_db) as conn:
        cursor = conn.cursor()
        
        # Create miner_attest_recent table
        cursor.execute("""
            CREATE TABLE miner_attest_recent (
                miner TEXT,
                device_arch TEXT,
                ts_ok INTEGER,
                fingerprint_passed INTEGER DEFAULT 1,
                entropy_score REAL,
                warthog_bonus REAL DEFAULT 1.0,
                wallet_address TEXT
            )
        """)
        
        # Create claims table
        cursor.execute("""
            CREATE TABLE claims (
                claim_id TEXT PRIMARY KEY,
                miner_id TEXT,
                epoch INTEGER,
                status TEXT,
                submitted_at INTEGER
            )
        """)
        
        # Insert test data
        current_ts = int(time.time())
        test_miner = "test-miner-g4"
        
        cursor.execute("""
            INSERT INTO miner_attest_recent
            (miner, device_arch, ts_ok, fingerprint_passed, entropy_score, wallet_address)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            test_miner,
            "g4",
            current_ts - 3600,  # 1 hour ago
            1,
            0.075,
            "RTC1TestWallet123456789"
        ))
        
        conn.commit()
    
    # Test eligibility check
    current_slot = (current_ts - GENESIS_TIMESTAMP) // BLOCK_TIME
    test_epoch = max(0, current_slot // 144 - 1)
    
    result = check_claim_eligibility(
        db_path=test_db,
        miner_id=test_miner,
        epoch=test_epoch,
        current_slot=current_slot,
        current_ts=current_ts
    )
    
    print(f"Miner ID: {result['miner_id']}")
    print(f"Epoch: {result['epoch']}")
    print(f"Eligible: {result['eligible']}")
    print(f"Reward: {result['reward_rtc']:.6f} RTC ({result['reward_urtc']} uRTC)")
    print(f"Reason: {result['reason']}")
    print(f"\nChecks:")
    for check, passed in result['checks'].items():
        status = "✓" if passed else "✗"
        print(f"  {status} {check}")
    
    if result['attestation']:
        print(f"\nAttestation:")
        print(f"  Device: {result['attestation']['device_arch']}")
        print(f"  Multiplier: {result['attestation']['antiquity_multiplier']:.2f}x")
    
    if result['wallet_address']:
        print(f"\nWallet: {result['wallet_address']}")
    
    print("\n=== Test Complete ===")
