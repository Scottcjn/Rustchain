// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import sqlite3
import hashlib
import time
import json
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
import threading

DB_PATH = "rustchain.db"

class AttestationValidator:
    def __init__(self, max_nonce_age_seconds=300, clock_skew_tolerance=60):
        self.max_nonce_age = max_nonce_age_seconds
        self.clock_skew = clock_skew_tolerance
        self.lock = threading.RLock()
        self._init_db()
        self._cleanup_old_nonces()

    def _init_db(self):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS attestation_nonces (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nonce TEXT UNIQUE NOT NULL,
                    miner_id TEXT NOT NULL,
                    timestamp INTEGER NOT NULL,
                    attestation_hash TEXT,
                    created_at INTEGER DEFAULT (strftime('%s', 'now'))
                )
            ''')

            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_nonce_timestamp
                ON attestation_nonces(timestamp)
            ''')

            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_nonce_miner
                ON attestation_nonces(miner_id)
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS challenge_nonces (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    challenge TEXT UNIQUE NOT NULL,
                    miner_id TEXT,
                    issued_at INTEGER NOT NULL,
                    used_at INTEGER,
                    expires_at INTEGER NOT NULL
                )
            ''')

            conn.commit()

    def _cleanup_old_nonces(self):
        cutoff_time = int(time.time()) - (self.max_nonce_age * 2)

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM attestation_nonces WHERE timestamp < ?",
                (cutoff_time,)
            )
            cursor.execute(
                "DELETE FROM challenge_nonces WHERE expires_at < ?",
                (int(time.time()),)
            )
            conn.commit()

    def validate_attestation(self, attestation_data: Dict[str, Any]) -> Dict[str, Any]:
        with self.lock:
            try:
                nonce = attestation_data.get('nonce')
                miner_id = attestation_data.get('miner_id')
                timestamp = attestation_data.get('timestamp')

                if not all([nonce, miner_id, timestamp]):
                    return {
                        'valid': False,
                        'error': 'MISSING_REQUIRED_FIELDS',
                        'message': 'Missing nonce, miner_id, or timestamp'
                    }

                # Check timestamp freshness
                current_time = int(time.time())
                if abs(current_time - timestamp) > (self.max_nonce_age + self.clock_skew):
                    return {
                        'valid': False,
                        'error': 'STALE_ATTESTATION',
                        'message': f'Attestation timestamp too old or too far in future',
                        'current_time': current_time,
                        'attestation_time': timestamp,
                        'max_age': self.max_nonce_age
                    }

                # Check for nonce replay
                if self._is_nonce_used(nonce):
                    return {
                        'valid': False,
                        'error': 'NONCE_REPLAY',
                        'message': f'Nonce {nonce} has already been used',
                        'nonce': nonce
                    }

                # Validate attestation format and content
                validation_result = self._validate_attestation_content(attestation_data)
                if not validation_result['valid']:
                    return validation_result

                # Store nonce to prevent replay
                attestation_hash = self._compute_attestation_hash(attestation_data)
                self._store_nonce(nonce, miner_id, timestamp, attestation_hash)

                return {
                    'valid': True,
                    'nonce': nonce,
                    'miner_id': miner_id,
                    'attestation_hash': attestation_hash,
                    'validated_at': current_time
                }

            except Exception as e:
                return {
                    'valid': False,
                    'error': 'VALIDATION_ERROR',
                    'message': f'Attestation validation failed: {str(e)}'
                }

    def _is_nonce_used(self, nonce: str) -> bool:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM attestation_nonces WHERE nonce = ? LIMIT 1",
                (nonce,)
            )
            return cursor.fetchone() is not None

    def _store_nonce(self, nonce: str, miner_id: str, timestamp: int, attestation_hash: str):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO attestation_nonces
                (nonce, miner_id, timestamp, attestation_hash)
                VALUES (?, ?, ?, ?)
            ''', (nonce, miner_id, timestamp, attestation_hash))
            conn.commit()

    def _validate_attestation_content(self, attestation_data: Dict[str, Any]) -> Dict[str, Any]:
        required_fields = ['nonce', 'miner_id', 'timestamp', 'proof']

        for field in required_fields:
            if field not in attestation_data:
                return {
                    'valid': False,
                    'error': 'MALFORMED_ATTESTATION',
                    'message': f'Missing required field: {field}'
                }

        # Validate proof structure
        proof = attestation_data.get('proof', {})
        if not isinstance(proof, dict):
            return {
                'valid': False,
                'error': 'INVALID_PROOF_FORMAT',
                'message': 'Proof must be a dictionary'
            }

        proof_fields = ['work_hash', 'merkle_root', 'difficulty']
        for field in proof_fields:
            if field not in proof:
                return {
                    'valid': False,
                    'error': 'INCOMPLETE_PROOF',
                    'message': f'Proof missing required field: {field}'
                }

        return {'valid': True}

    def _compute_attestation_hash(self, attestation_data: Dict[str, Any]) -> str:
        attestation_str = json.dumps(attestation_data, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(attestation_str.encode()).hexdigest()

    def issue_challenge(self, miner_id: Optional[str] = None, ttl_seconds: int = 300) -> Dict[str, Any]:
        with self.lock:
            challenge = hashlib.sha256(f"{time.time()}{miner_id or 'anonymous'}".encode()).hexdigest()[:16]
            issued_at = int(time.time())
            expires_at = issued_at + ttl_seconds

            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO challenge_nonces
                    (challenge, miner_id, issued_at, expires_at)
                    VALUES (?, ?, ?, ?)
                ''', (challenge, miner_id, issued_at, expires_at))
                conn.commit()

            return {
                'challenge': challenge,
                'issued_at': issued_at,
                'expires_at': expires_at,
                'ttl': ttl_seconds
            }

    def validate_challenge_response(self, challenge: str, attestation_data: Dict[str, Any]) -> Dict[str, Any]:
        with self.lock:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT miner_id, expires_at, used_at
                    FROM challenge_nonces
                    WHERE challenge = ?
                ''', (challenge,))

                result = cursor.fetchone()
                if not result:
                    return {
                        'valid': False,
                        'error': 'INVALID_CHALLENGE',
                        'message': 'Challenge not found or expired'
                    }

                miner_id, expires_at, used_at = result
                current_time = int(time.time())

                if current_time > expires_at:
                    return {
                        'valid': False,
                        'error': 'CHALLENGE_EXPIRED',
                        'message': 'Challenge has expired'
                    }

                if used_at:
                    return {
                        'valid': False,
                        'error': 'CHALLENGE_ALREADY_USED',
                        'message': 'Challenge has already been used'
                    }

                # Mark challenge as used
                cursor.execute('''
                    UPDATE challenge_nonces
                    SET used_at = ?
                    WHERE challenge = ?
                ''', (current_time, challenge))
                conn.commit()

            # Validate the attestation with the challenge
            attestation_data['challenge'] = challenge
            return self.validate_attestation(attestation_data)

    def get_nonce_stats(self) -> Dict[str, Any]:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # Count active nonces
            cutoff = int(time.time()) - self.max_nonce_age
            cursor.execute(
                "SELECT COUNT(*) FROM attestation_nonces WHERE timestamp > ?",
                (cutoff,)
            )
            active_nonces = cursor.fetchone()[0]

            # Count total nonces
            cursor.execute("SELECT COUNT(*) FROM attestation_nonces")
            total_nonces = cursor.fetchone()[0]

            # Count active challenges
            cursor.execute(
                "SELECT COUNT(*) FROM challenge_nonces WHERE expires_at > ? AND used_at IS NULL",
                (int(time.time()),)
            )
            active_challenges = cursor.fetchone()[0]

            return {
                'active_nonces': active_nonces,
                'total_nonces': total_nonces,
                'active_challenges': active_challenges,
                'max_nonce_age': self.max_nonce_age,
                'clock_skew_tolerance': self.clock_skew
            }

    def cleanup_expired_data(self):
        self._cleanup_old_nonces()
