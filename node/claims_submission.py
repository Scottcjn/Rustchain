#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
RIP-305 Track D: Claims Submission & Validation
================================================

Provides secure claim submission with signature verification,
duplicate prevention, and audit logging.

Usage:
    from claims_submission import submit_claim, validate_claim_signature
    
    result = submit_claim(
        db_path="/path/to/node.db",
        miner_id="n64-scott-unit1",
        epoch=1234,
        wallet_address="RTC1abc123...",
        signature="<Ed25519 signature>",
        public_key="<Ed25519 public key>",
        ip_address="192.168.1.1",
        user_agent="Mozilla/5.0..."
    )
"""

import sqlite3
import time
import json
import hashlib
import hmac
from typing import Dict, Optional, Any, Tuple
from datetime import datetime

try:
    from nacl.signing import VerifyKey
    from nacl.exceptions import BadSignatureError
    HAVE_NACL = True
except ImportError:
    HAVE_NACL = False
    print("[WARN] PyNaCl not available — claim signature verification will REJECT all claims")

try:
    from claims_eligibility import (
        check_claim_eligibility,
        validate_miner_id_format
    )
except ImportError:
    # Fallback if running standalone
    def check_claim_eligibility(*args, **kwargs):
        return {"eligible": False, "reason": "module_not_loaded"}
    
    def validate_miner_id_format(miner_id: str) -> bool:
        if not miner_id or not isinstance(miner_id, str):
            return False
        if len(miner_id) > 128:
            return False
        import re
        return bool(re.match(r'^[a-zA-Z0-9_-]+$', miner_id))


class ClaimsSubmissionError(Exception):
    """Base exception for claims submission errors"""
    pass


class InvalidSignatureError(ClaimsSubmissionError):
    """Cryptographic signature verification failed"""
    pass


class DuplicateClaimError(ClaimsSubmissionError):
    """Claim already exists for this miner/epoch"""
    pass


class IneligibleMinerError(ClaimsSubmissionError):
    """Miner is not eligible to claim rewards"""
    pass


class InvalidWalletAddressError(ClaimsSubmissionError):
    """Wallet address format is invalid"""
    pass


def validate_wallet_address_format(wallet_address: str) -> bool:
    """
    Validate RustChain wallet address format
    
    Valid addresses:
    - Start with 'RTC' prefix
    - Followed by 20-40 alphanumeric characters
    - Case-insensitive
    """
    if not wallet_address or not isinstance(wallet_address, str):
        return False
    
    import re
    pattern = r'^RTC[a-zA-Z0-9]{20,40}$'
    return bool(re.match(pattern, wallet_address, re.IGNORECASE))


def wallet_addresses_match(submitted_wallet: str, registered_wallet: str) -> bool:
    """
    Compare RustChain wallet addresses using the same case-insensitive
    semantics as the address format validator.
    """
    if not isinstance(submitted_wallet, str) or not isinstance(registered_wallet, str):
        return False
    return submitted_wallet.casefold() == registered_wallet.casefold()


def create_claim_payload(
    miner_id: str,
    epoch: int,
    wallet_address: str,
    timestamp: int
) -> str:
    """
    Create canonical JSON payload for signature
    
    The payload is deterministic (sorted keys, no extra whitespace)
    to ensure consistent signature verification.
    """
    payload = {
        "miner_id": miner_id,
        "epoch": epoch,
        "wallet_address": wallet_address,
        "timestamp": timestamp
    }
    return json.dumps(payload, sort_keys=True, separators=(',', ':'))


def generate_claim_id(miner_id: str, epoch: int) -> str:
    """
    Generate unique claim ID
    
    Format: claim_{epoch}_{miner_id}
    """
    return f"claim_{epoch}_{miner_id}"


def validate_claim_signature(
    payload: str,
    signature: str,
    public_key: str
) -> Tuple[bool, Optional[str]]:
    """
    Verify Ed25519 signature on claim payload
    
    Args:
        payload: Canonical JSON payload string
        signature: Hex-encoded Ed25519 signature
        public_key: Hex-encoded Ed25519 public key
    
    Returns:
        (valid: bool, error_message: str or None)
    """
    if not HAVE_NACL:
        # SECURITY: Fail closed — reject claims when the crypto library
        # is unavailable rather than silently accepting any signature.
        return False, "Ed25519 library (PyNaCl) is not installed — cannot verify signatures"
    
    try:
        # Decode hex strings
        signature_bytes = bytes.fromhex(signature)
        public_key_bytes = bytes.fromhex(public_key)
        
        # Verify signature
        verify_key = VerifyKey(public_key_bytes)
        verify_key.verify(payload.encode('utf-8'), signature_bytes)
        
        return True, None
    except BadSignatureError:
        return False, "Signature verification failed"
    except ValueError as e:
        return False, f"Invalid key or signature format: {e}"
    except Exception as e:
        return False, f"Signature verification error: {e}"


def create_claim_record(
    db_path: str,
    claim_id: str,
    miner_id: str,
    epoch: int,
    wallet_address: str,
    reward_urtc: int,
    signature: str,
    public_key: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create claim record in database
    
    Returns:
        Claim record details
    """
    current_ts = int(time.time())
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # Ensure claims table exists
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS claims (
                    claim_id TEXT PRIMARY KEY,
                    miner_id TEXT NOT NULL,
                    epoch INTEGER NOT NULL,
                    wallet_address TEXT NOT NULL,
                    reward_urtc INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    submitted_at INTEGER NOT NULL,
                    verified_at INTEGER,
                    settled_at INTEGER,
                    transaction_hash TEXT,
                    settlement_batch TEXT,
                    rejection_reason TEXT,
                    signature TEXT NOT NULL,
                    public_key TEXT NOT NULL,
                    ip_address TEXT,
                    user_agent TEXT,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL,
                    UNIQUE(miner_id, epoch)
                )
            """)
            
            # Create indexes if they don't exist
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_claims_miner ON claims(miner_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_claims_epoch ON claims(epoch)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_claims_status ON claims(status)
            """)
            
            # Insert claim record
            cursor.execute("""
                INSERT INTO claims (
                    claim_id, miner_id, epoch, wallet_address,
                    reward_urtc, status, submitted_at, signature,
                    public_key, ip_address, user_agent, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?, ?, ?)
            """, (
                claim_id,
                miner_id,
                epoch,
                wallet_address,
                reward_urtc,
                current_ts,
                signature,
                public_key,
                ip_address,
                user_agent,
                current_ts,
                current_ts
            ))
            
            # Create audit log entry
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS claims_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    claim_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    actor TEXT,
                    details TEXT,
                    timestamp INTEGER NOT NULL
                )
            """)
            
            cursor.execute("""
                INSERT INTO claims_audit (claim_id, action, actor, details, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (
                claim_id,
                'claim_submitted',
                miner_id,
                json.dumps({
                    "epoch": epoch,
                    "wallet_address": wallet_address,
                    "reward_urtc": reward_urtc,
                    "ip_address": ip_address
                }),
                current_ts
            ))
            
            conn.commit()
            
            return {
                "claim_id": claim_id,
                "status": "pending",
                "submitted_at": current_ts,
                "estimated_settlement": current_ts + 1800  # 30 minutes
            }
    except sqlite3.IntegrityError:
        raise DuplicateClaimError(f"Claim already exists for miner {miner_id} epoch {epoch}")
    except sqlite3.Error as e:
        raise ClaimsSubmissionError(f"Database error: {e}")


def update_claim_status(
    db_path: str,
    claim_id: str,
    status: str,
    details: Optional[Dict] = None
) -> bool:
    """
    Update claim status and create audit log entry
    
    Args:
        db_path: Database path
        claim_id: Claim ID to update
        status: New status (pending, verifying, approved, settled, rejected, failed)
        details: Optional additional details
    
    Returns:
        True if update successful
    """
    current_ts = int(time.time())
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # Update claim status
            cursor.execute("""
                UPDATE claims
                SET status = ?, updated_at = ?, verified_at = ?
                WHERE claim_id = ?
            """, (
                status,
                current_ts,
                current_ts if status in ['approved', 'rejected'] else None,
                claim_id
            ))
            
            # Add details if provided
            if details:
                if status == 'settled':
                    cursor.execute("""
                        UPDATE claims
                        SET transaction_hash = ?, settlement_batch = ?, settled_at = ?
                        WHERE claim_id = ?
                    """, (
                        details.get('transaction_hash'),
                        details.get('settlement_batch'),
                        current_ts,
                        claim_id
                    ))
                elif status == 'rejected':
                    cursor.execute("""
                        UPDATE claims
                        SET rejection_reason = ?
                        WHERE claim_id = ?
                    """, (
                        details.get('reason'),
                        claim_id
                    ))
            
            # Create audit log entry
            cursor.execute("""
                INSERT INTO claims_audit (claim_id, action, actor, details, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (
                claim_id,
                f'claim_{status}',
                'system',
                json.dumps(details) if details else None,
                current_ts
            ))
            
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        print(f"[CLAIMS] Error updating status: {e}")
        return False


def get_claim_status(
    db_path: str,
    claim_id: str
) -> Optional[Dict[str, Any]]:
    """
    Get current claim status
    
    Returns:
        Claim details dict or None if not found
    """
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM claims WHERE claim_id = ?
            """, (claim_id,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            return {
                "claim_id": row["claim_id"],
                "miner_id": row["miner_id"],
                "epoch": row["epoch"],
                "status": row["status"],
                "submitted_at": row["submitted_at"],
                "verified_at": row["verified_at"],
                "settled_at": row["settled_at"],
                "reward_urtc": row["reward_urtc"],
                "reward_rtc": row["reward_urtc"] / 1_000_000,
                "wallet_address": row["wallet_address"],
                "transaction_hash": row["transaction_hash"],
                "settlement_batch": row["settlement_batch"],
                "rejection_reason": row["rejection_reason"]
            }
    except sqlite3.Error as e:
        print(f"[CLAIMS] Error getting claim status: {e}")
        return None


def submit_claim(
    db_path: str,
    miner_id: str,
    epoch: int,
    wallet_address: str,
    signature: str,
    public_key: str,
    current_slot: int,
    current_ts: int,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    skip_signature_verify: bool = False
) -> Dict[str, Any]:
    """
    Submit a reward claim with full validation
    
    Args:
        db_path: Path to node SQLite database
        miner_id: Unique miner identifier
        epoch: Epoch number to claim rewards for
        wallet_address: Destination wallet address
        signature: Ed25519 signature (hex-encoded)
        public_key: Ed25519 public key (hex-encoded)
        current_slot: Current blockchain slot number
        current_ts: Current Unix timestamp
        ip_address: Requester IP address (for audit)
        user_agent: Requester user agent (for audit)
        skip_signature_verify: Skip signature verification (testing only)
    
    Returns:
        {
            "success": bool,
            "claim_id": str,
            "status": str,
            "submitted_at": int,
            "estimated_settlement": int,
            "reward_urtc": int,
            "reward_rtc": float,
            "error": str or None
        }
    """
    result = {
        "success": False,
        "claim_id": None,
        "status": None,
        "submitted_at": None,
        "estimated_settlement": None,
        "reward_urtc": 0,
        "reward_rtc": 0.0,
        "error": None
    }
    
    # Validate miner ID format
    if not validate_miner_id_format(miner_id):
        result["error"] = "invalid_miner_id"
        return result
    
    # Validate wallet address format
    if not validate_wallet_address_format(wallet_address):
        result["error"] = "invalid_wallet_address"
        return result
    
    # Check eligibility
    eligibility = check_claim_eligibility(
        db_path=db_path,
        miner_id=miner_id,
        epoch=epoch,
        current_slot=current_slot,
        current_ts=current_ts
    )
    
    if not eligibility["eligible"]:
        result["error"] = f"ineligible: {eligibility['reason']}"
        return result

    registered_wallet = eligibility.get("wallet_address")
    if not wallet_addresses_match(wallet_address, registered_wallet):
        result["error"] = "wallet_address_mismatch"
        return result
    
    # Verify signature (unless skipped for testing)
    if not skip_signature_verify:
        timestamp = current_ts
        payload = create_claim_payload(miner_id, epoch, wallet_address, timestamp)
        
        valid, error = validate_claim_signature(payload, signature, public_key)
        if not valid:
            result["error"] = f"invalid_signature: {error}"
            return result
    
    # Generate claim ID
    claim_id = generate_claim_id(miner_id, epoch)
    
    # Create claim record
    try:
        claim_record = create_claim_record(
            db_path=db_path,
            claim_id=claim_id,
            miner_id=miner_id,
            epoch=epoch,
            wallet_address=wallet_address,
            reward_urtc=eligibility["reward_urtc"],
            signature=signature,
            public_key=public_key,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        result["success"] = True
        result["claim_id"] = claim_id
        result["status"] = claim_record["status"]
        result["submitted_at"] = claim_record["submitted_at"]
        result["estimated_settlement"] = claim_record["estimated_settlement"]
        result["reward_urtc"] = eligibility["reward_urtc"]
        result["reward_rtc"] = eligibility["reward_urtc"] / 1_000_000
        
        return result
    except DuplicateClaimError as e:
        result["error"] = str(e)
        return result
    except ClaimsSubmissionError as e:
        result["error"] = str(e)
        return result


def get_claim_history(
    db_path: str,
    miner_id: str,
    limit: int = 20
) -> Dict[str, Any]:
    """
    Get claim history for a miner
    
    Returns:
        {
            "miner_id": str,
            "total_claims": int,
            "total_claimed_urtc": int,
            "claims": [
                {
                    "claim_id": str,
                    "epoch": int,
                    "status": str,
                    "reward_urtc": int,
                    "submitted_at": int,
                    "settled_at": int or None
                }
            ]
        }
    """
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM claims
                WHERE miner_id = ?
                ORDER BY submitted_at DESC
                LIMIT ?
            """, (miner_id, limit))
            
            claims = []
            total_claimed = 0
            
            for row in cursor.fetchall():
                claims.append({
                    "claim_id": row["claim_id"],
                    "epoch": row["epoch"],
                    "status": row["status"],
                    "reward_urtc": row["reward_urtc"],
                    "submitted_at": row["submitted_at"],
                    "settled_at": row["settled_at"]
                })
                
                if row["status"] == "settled":
                    total_claimed += row["reward_urtc"]
            
            # Get total count
            cursor.execute("""
                SELECT COUNT(*) FROM claims WHERE miner_id = ?
            """, (miner_id,))
            total_count = cursor.fetchone()[0]
            
            return {
                "miner_id": miner_id,
                "total_claims": total_count,
                "total_claimed_urtc": total_claimed,
                "total_claimed_rtc": total_claimed / 1_000_000,
                "claims": claims
            }
    except sqlite3.Error as e:
        print(f"[CLAIMS] Error getting claim history: {e}")
        return {
            "miner_id": miner_id,
            "total_claims": 0,
            "total_claimed_urtc": 0,
            "claims": []
        }


# Example usage and testing
if __name__ == "__main__":
    import os
    
    print("=== RIP-305 Claims Submission Test ===\n")
    
    # Create test database
    test_db = ":memory:"
    
    with sqlite3.connect(test_db) as conn:
        cursor = conn.cursor()
        
        # Create required tables
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
        
        # Insert test data
        current_ts = int(time.time())
        test_miner = "test-miner-g4"
        test_wallet = "RTC1TestWalletAddress1234567890"
        
        cursor.execute("""
            INSERT INTO miner_attest_recent
            (miner, device_arch, ts_ok, fingerprint_passed, entropy_score, wallet_address)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            test_miner,
            "g4",
            current_ts - 3600,
            1,
            0.075,
            test_wallet
        ))
        
        conn.commit()
    
    # Test claim submission (with signature verification skipped for testing)
    from claims_eligibility import GENESIS_TIMESTAMP, BLOCK_TIME
    
    current_slot = (current_ts - GENESIS_TIMESTAMP) // BLOCK_TIME
    test_epoch = max(0, current_slot // 144 - 1)
    
    # Generate mock signature (in production, this would be real Ed25519)
    mock_payload = create_claim_payload(test_miner, test_epoch, test_wallet, current_ts)
    mock_signature = "0" * 128  # Mock 64-byte signature in hex
    mock_public_key = "1" * 64  # Mock 32-byte public key in hex
    
    result = submit_claim(
        db_path=test_db,
        miner_id=test_miner,
        epoch=test_epoch,
        wallet_address=test_wallet,
        signature=mock_signature,
        public_key=mock_public_key,
        current_slot=current_slot,
        current_ts=current_ts,
        ip_address="127.0.0.1",
        user_agent="TestClient/1.0",
        skip_signature_verify=True
    )
    
    print(f"Claim Submission Result:")
    print(f"  Success: {result['success']}")
    print(f"  Claim ID: {result['claim_id']}")
    print(f"  Status: {result['status']}")
    print(f"  Reward: {result['reward_rtc']:.6f} RTC")
    print(f"  Error: {result['error']}")
    
    # Test getting claim status
    if result['success']:
        status = get_claim_status(test_db, result['claim_id'])
        print(f"\nClaim Status:")
        print(f"  Claim ID: {status['claim_id']}")
        print(f"  Epoch: {status['epoch']}")
        print(f"  Status: {status['status']}")
        print(f"  Reward: {status['reward_rtc']:.6f} RTC")
        print(f"  Wallet: {status['wallet_address']}")
    
    # Test claim history
    history = get_claim_history(test_db, test_miner)
    print(f"\nClaim History:")
    print(f"  Total Claims: {history['total_claims']}")
    print(f"  Total Claimed: {history['total_claimed_rtc']:.6f} RTC")
    
    print("\n=== Test Complete ===")
