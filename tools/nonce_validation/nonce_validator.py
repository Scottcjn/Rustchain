#!/usr/bin/env python3
"""
Nonce Binding & Attestation Replay Prevention

Server-side nonce tracking and replay prevention for RustChain attestation protocol.

Features:
- Server-side nonce tracking table (used_nonces)
- Duplicate nonce rejection
- Timestamp freshness validation (±60s default)
- Optional challenge-response flow
- TTL-based nonce expiry

Usage:
    python nonce_validator.py --db_path rustchain.db
"""

import sqlite3
import time
import hashlib
import secrets
import argparse
from datetime import datetime, timedelta
from typing import Tuple, Optional, Dict
from dataclasses import dataclass


@dataclass
class Attestation:
    """An attestation submission."""
    miner_id: str
    nonce: str
    timestamp: float
    payload: str


class NonceValidator:
    """Validates nonces and prevents replay attacks."""
    
    def __init__(self, db_path: str, freshness_window: int = 60):
        self.db_path = db_path
        self.freshness_window = freshness_window
        self.conn = sqlite3.connect(db_path)
        self._init_table()
    
    def _init_table(self):
        """Create nonce tracking table."""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS used_nonces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                miner_id TEXT NOT NULL,
                nonce_hash TEXT NOT NULL,
                timestamp REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                UNIQUE(miner_id, nonce_hash)
            )
        """)
        
        # Index for O(1) lookup
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_nonce_lookup 
            ON used_nonces(miner_id, nonce_hash)
        """)
        
        self.conn.commit()
    
    def _hash_nonce(self, nonce: str) -> str:
        """Hash nonce for storage."""
        return hashlib.sha256(nonce.encode()).hexdigest()[:32]
    
    def _cleanup_expired(self):
        """Remove expired nonces."""
        self.conn.execute("""
            DELETE FROM used_nonces 
            WHERE expires_at < datetime('now')
        """)
        self.conn.commit()
    
    def validate_nonce(self, miner_id: str, nonce: str, timestamp: Optional[float] = None) -> Tuple[bool, str]:
        """
        Validate a nonce for attestation.
        
        Returns: (is_valid, error_message)
        """
        # Cleanup expired nonces periodically
        if secrets.randbelow(100) < 5:  # 5% chance
            self._cleanup_expired()
        
        # Check timestamp freshness
        if timestamp is None:
            timestamp = time.time()
        
        server_time = time.time()
        time_diff = abs(server_time - timestamp)
        
        if time_diff > self.freshness_window:
            return False, f"Timestamp out of range (diff: {time_diff:.1f}s, max: {self.freshness_window}s)"
        
        # Check for duplicate nonce
        nonce_hash = self._hash_nonce(nonce)
        
        cursor = self.conn.execute("""
            SELECT id FROM used_nonces 
            WHERE miner_id = ? AND nonce_hash = ?
        """, (miner_id, nonce_hash))
        
        if cursor.fetchone():
            return False, "Duplicate nonce - possible replay attack"
        
        # Store the nonce
        expires_at = datetime.now() + timedelta(days=1)
        
        try:
            self.conn.execute("""
                INSERT INTO used_nonces (miner_id, nonce_hash, timestamp, expires_at)
                VALUES (?, ?, ?, ?)
            """, (miner_id, nonce_hash, timestamp, expires_at))
            self.conn.commit()
            return True, ""
        except sqlite3.IntegrityError:
            return False, "Duplicate nonce detected (race condition)"
    
    def generate_challenge(self, miner_id: str) -> str:
        """Generate a server challenge for challenge-response flow."""
        challenge = secrets.token_urlsafe(32)
        challenge_hash = self._hash_nonce(challenge)
        
        # Store challenge
        expires_at = datetime.now() + timedelta(minutes=5)
        
        self.conn.execute("""
            INSERT OR REPLACE INTO used_nonces (miner_id, nonce_hash, timestamp, expires_at)
            VALUES (?, ?, ?, ?)
        """, (miner_id, challenge_hash, time.time(), expires_at))
        self.conn.commit()
        
        return challenge
    
    def validate_challenge(self, miner_id: str, challenge: str) -> bool:
        """Validate a challenge-response."""
        challenge_hash = self._hash_nonce(challenge)
        
        cursor = self.conn.execute("""
            SELECT id FROM used_nonces 
            WHERE miner_id = ? AND nonce_hash = ? AND expires_at > datetime('now')
        """, (miner_id, challenge_hash))
        
        return cursor.fetchone() is not None
    
    def get_stats(self) -> Dict:
        """Get nonce tracking statistics."""
        cursor = self.conn.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(DISTINCT miner_id) as unique_miners,
                COUNT(CASE WHEN expires_at > datetime('now') THEN 1 END) as active
            FROM used_nonces
        """)
        row = cursor.fetchone()
        
        return {
            "total_nonces": row[0],
            "unique_miners": row[1],
            "active_nonces": row[2]
        }
    
    def close(self):
        """Close database connection."""
        self.conn.close()


class AttestationValidator:
    """Validates attestation submissions with nonce checking."""
    
    def __init__(self, db_path: str, freshness_window: int = 60, require_challenge: bool = False):
        self.nonce_validator = NonceValidator(db_path, freshness_window)
        self.require_challenge = require_challenge
    
    def validate(self, attestation: Attestation, challenge: Optional[str] = None) -> Tuple[bool, str]:
        """
        Validate a complete attestation.
        
        Returns: (is_valid, error_message)
        """
        # Check challenge-response if required
        if self.require_challenge:
            if not challenge:
                return False, "Challenge required but not provided"
            
            if not self.nonce_validator.validate_challenge(attestation.miner_id, challenge):
                return False, "Invalid or expired challenge"
        
        # Validate nonce
        is_valid, error = self.nonce_validator.validate_nonce(
            attestation.miner_id,
            attestation.nonce,
            attestation.timestamp
        )
        
        if not is_valid:
            return False, f"Nonce validation failed: {error}"
        
        return True, ""
    
    def close(self):
        """Close validator."""
        self.nonce_validator.close()


def main():
    parser = argparse.ArgumentParser(description="Nonce Validation Tool")
    parser.add_argument("--db_path", type=str, default="rustchain.db", help="Database path")
    parser.add_argument("--freshness_window", type=int, default=60, help="Freshness window in seconds")
    parser.add_argument("--miner_id", type=str, help="Miner ID to test")
    parser.add_argument("--nonce", type=str, help="Nonce to validate")
    parser.add_argument("--timestamp", type=float, help="Timestamp of attestation")
    parser.add_argument("--stats", action="store_true", help="Show statistics")
    args = parser.parse_args()
    
    validator = NonceValidator(args.db_path, args.freshness_window)
    
    if args.stats:
        stats = validator.get_stats()
        print("Nonce Statistics:")
        print(f"  Total nonces: {stats['total_nonces']}")
        print(f"  Unique miners: {stats['unique_miners']}")
        print(f"  Active nonces: {stats['active_nonces']}")
    
    elif args.miner_id and args.nonce:
        is_valid, error = validator.validate_nonce(
            args.miner_id,
            args.nonce,
            args.timestamp
        )
        
        if is_valid:
            print(f"✓ Nonce valid for {args.miner_id}")
        else:
            print(f"✗ Validation failed: {error}")
    
    else:
        print("Specify --miner_id --nonce or --stats")
    
    validator.close()


if __name__ == "__main__":
    main()
