// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import sqlite3
import time
import hashlib
import secrets
import json
from threading import RLock
from typing import Optional, Dict, Tuple, Any

DB_PATH = 'rustchain.db'
NONCE_TABLE = 'nonce_attestations'
CHALLENGE_TABLE = 'active_challenges'

class NonceAttestationSecurity:
    def __init__(self,
                 freshness_window_seconds: int = 300,
                 clock_skew_tolerance_seconds: int = 30,
                 challenge_timeout_seconds: int = 180):
        self.freshness_window = freshness_window_seconds
        self.clock_skew = clock_skew_tolerance_seconds
        self.challenge_timeout = challenge_timeout_seconds
        self._lock = RLock()
        self._init_tables()

    def _init_tables(self):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS nonce_attestations (
                    nonce_hash TEXT PRIMARY KEY,
                    miner_id TEXT NOT NULL,
                    timestamp INTEGER NOT NULL,
                    created_at INTEGER NOT NULL,
                    attestation_data TEXT
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS active_challenges (
                    challenge_id TEXT PRIMARY KEY,
                    miner_id TEXT NOT NULL,
                    nonce TEXT NOT NULL,
                    issued_at INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL
                )
            ''')

            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_nonce_miner
                ON nonce_attestations(miner_id, timestamp)
            ''')

            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_challenge_miner
                ON active_challenges(miner_id, expires_at)
            ''')

            conn.commit()

    def issue_challenge(self, miner_id: str) -> Dict[str, Any]:
        """Issue a fresh challenge/nonce to a miner"""
        with self._lock:
            challenge_id = secrets.token_hex(16)
            nonce = secrets.token_hex(32)
            now = int(time.time())
            expires_at = now + self.challenge_timeout

            with sqlite3.connect(DB_PATH) as conn:
                # Clean up expired challenges first
                conn.execute(
                    'DELETE FROM active_challenges WHERE expires_at < ?',
                    (now,)
                )

                # Insert new challenge
                conn.execute('''
                    INSERT INTO active_challenges
                    (challenge_id, miner_id, nonce, issued_at, expires_at)
                    VALUES (?, ?, ?, ?, ?)
                ''', (challenge_id, miner_id, nonce, now, expires_at))

                conn.commit()

            return {
                'challenge_id': challenge_id,
                'nonce': nonce,
                'issued_at': now,
                'expires_at': expires_at,
                'timeout_seconds': self.challenge_timeout
            }

    def validate_nonce_attestation(self,
                                   miner_id: str,
                                   nonce: str,
                                   attestation_timestamp: int,
                                   attestation_data: Optional[str] = None,
                                   challenge_id: Optional[str] = None) -> Tuple[bool, str]:
        """
        Validate nonce attestation with replay prevention and freshness checks
        Returns (is_valid, failure_reason)
        """
        with self._lock:
            now = int(time.time())
            nonce_hash = hashlib.sha256(f"{miner_id}:{nonce}".encode()).hexdigest()

            # Check timestamp freshness with clock skew tolerance
            min_timestamp = now - self.freshness_window - self.clock_skew
            max_timestamp = now + self.clock_skew

            if attestation_timestamp < min_timestamp:
                return False, f"Attestation too old: {attestation_timestamp} < {min_timestamp}"

            if attestation_timestamp > max_timestamp:
                return False, f"Attestation timestamp in future: {attestation_timestamp} > {max_timestamp}"

            with sqlite3.connect(DB_PATH) as conn:
                # Check for duplicate nonce
                cursor = conn.execute(
                    'SELECT nonce_hash FROM nonce_attestations WHERE nonce_hash = ?',
                    (nonce_hash,)
                )
                if cursor.fetchone():
                    return False, f"Nonce already used: {nonce_hash[:16]}..."

                # If challenge_id provided, validate challenge-response flow
                if challenge_id:
                    cursor = conn.execute('''
                        SELECT nonce, expires_at FROM active_challenges
                        WHERE challenge_id = ? AND miner_id = ?
                    ''', (challenge_id, miner_id))

                    challenge_row = cursor.fetchone()
                    if not challenge_row:
                        return False, f"Invalid or unknown challenge_id: {challenge_id}"

                    expected_nonce, expires_at = challenge_row
                    if now > expires_at:
                        return False, f"Challenge expired at {expires_at}, now {now}"

                    if nonce != expected_nonce:
                        return False, f"Nonce mismatch for challenge {challenge_id}"

                    # Remove used challenge
                    conn.execute(
                        'DELETE FROM active_challenges WHERE challenge_id = ?',
                        (challenge_id,)
                    )

                # Record the attestation nonce
                conn.execute('''
                    INSERT INTO nonce_attestations
                    (nonce_hash, miner_id, timestamp, created_at, attestation_data)
                    VALUES (?, ?, ?, ?, ?)
                ''', (nonce_hash, miner_id, attestation_timestamp, now, attestation_data))

                # Cleanup old attestations beyond freshness window
                cleanup_threshold = now - (self.freshness_window * 2)
                conn.execute(
                    'DELETE FROM nonce_attestations WHERE created_at < ?',
                    (cleanup_threshold,)
                )

                conn.commit()

            return True, "Valid attestation"

    def get_attestation_stats(self, miner_id: str = None) -> Dict[str, Any]:
        """Get statistics about attestation activity"""
        with sqlite3.connect(DB_PATH) as conn:
            if miner_id:
                cursor = conn.execute('''
                    SELECT COUNT(*), MIN(timestamp), MAX(timestamp)
                    FROM nonce_attestations WHERE miner_id = ?
                ''', (miner_id,))
            else:
                cursor = conn.execute('''
                    SELECT COUNT(*), MIN(timestamp), MAX(timestamp)
                    FROM nonce_attestations
                ''')

            count, min_ts, max_ts = cursor.fetchone()

            # Get unique miners count
            cursor = conn.execute('SELECT COUNT(DISTINCT miner_id) FROM nonce_attestations')
            unique_miners = cursor.fetchone()[0]

            # Get pending challenges
            now = int(time.time())
            cursor = conn.execute(
                'SELECT COUNT(*) FROM active_challenges WHERE expires_at > ?',
                (now,)
            )
            pending_challenges = cursor.fetchone()[0]

            return {
                'total_attestations': count or 0,
                'unique_miners': unique_miners or 0,
                'oldest_timestamp': min_ts,
                'newest_timestamp': max_ts,
                'pending_challenges': pending_challenges,
                'freshness_window': self.freshness_window,
                'clock_skew_tolerance': self.clock_skew
            }

    def cleanup_expired_data(self) -> int:
        """Clean up expired challenges and old attestations"""
        now = int(time.time())
        cleanup_threshold = now - (self.freshness_window * 2)

        with sqlite3.connect(DB_PATH) as conn:
            # Clean expired challenges
            cursor = conn.execute(
                'DELETE FROM active_challenges WHERE expires_at < ?',
                (now,)
            )
            expired_challenges = cursor.rowcount

            # Clean old attestations
            cursor = conn.execute(
                'DELETE FROM nonce_attestations WHERE created_at < ?',
                (cleanup_threshold,)
            )
            old_attestations = cursor.rowcount

            conn.commit()

            return expired_challenges + old_attestations

# Global security instance
nonce_security = NonceAttestationSecurity()

def validate_attestation_nonce(miner_id: str, nonce: str, timestamp: int,
                               attestation_data: str = None,
                               challenge_id: str = None) -> Tuple[bool, str]:
    """
    Public API function for validating attestation nonces
    """
    return nonce_security.validate_nonce_attestation(
        miner_id, nonce, timestamp, attestation_data, challenge_id
    )

def request_challenge(miner_id: str) -> Dict[str, Any]:
    """
    Public API function for requesting a fresh challenge
    """
    return nonce_security.issue_challenge(miner_id)
