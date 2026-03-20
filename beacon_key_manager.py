// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import sqlite3
import time
import json
from typing import Optional, Dict, List, Tuple
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.exceptions import InvalidSignature
import os

DB_PATH = 'beacon_keys.db'
DEFAULT_TTL = 30 * 24 * 60 * 60  # 30 days in seconds

class BeaconKeyManager:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_database()

    def _init_database(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS agent_keys (
                    agent_id TEXT PRIMARY KEY,
                    public_key TEXT NOT NULL,
                    first_seen INTEGER NOT NULL,
                    last_seen INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL,
                    rotation_count INTEGER DEFAULT 0,
                    is_revoked INTEGER DEFAULT 0,
                    revoked_at INTEGER,
                    metadata TEXT
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS key_rotation_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT NOT NULL,
                    old_key_hash TEXT NOT NULL,
                    new_key_hash TEXT NOT NULL,
                    rotated_at INTEGER NOT NULL,
                    signature TEXT NOT NULL,
                    FOREIGN KEY (agent_id) REFERENCES agent_keys (agent_id)
                )
            ''')

            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_agent_keys_expires
                ON agent_keys (expires_at)
            ''')

            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_rotation_log_agent
                ON key_rotation_log (agent_id)
            ''')

            conn.commit()

    def _key_hash(self, public_key_pem: str) -> str:
        """Generate a hash of the public key for rotation tracking."""
        digest = hashes.Hash(hashes.SHA256())
        digest.update(public_key_pem.encode())
        return digest.finalize().hex()[:16]

    def learn_key(self, agent_id: str, public_key_pem: str,
                  ttl: int = DEFAULT_TTL, metadata: Dict = None) -> bool:
        """Learn a new key using TOFU principle."""
        current_time = int(time.time())
        expires_at = current_time + ttl
        metadata_json = json.dumps(metadata or {})

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Check if we already have a key for this agent
            cursor.execute(
                'SELECT public_key, is_revoked FROM agent_keys WHERE agent_id = ?',
                (agent_id,)
            )
            existing = cursor.fetchone()

            if existing:
                # Key already exists - don't overwrite (TOFU principle)
                return False

            cursor.execute('''
                INSERT INTO agent_keys
                (agent_id, public_key, first_seen, last_seen, expires_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (agent_id, public_key_pem, current_time, current_time,
                  expires_at, metadata_json))

            conn.commit()
            return True

    def update_heartbeat(self, agent_id: str, ttl: int = DEFAULT_TTL) -> bool:
        """Update last_seen and extend expiration for an agent."""
        current_time = int(time.time())
        expires_at = current_time + ttl

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE agent_keys
                SET last_seen = ?, expires_at = ?
                WHERE agent_id = ? AND is_revoked = 0
            ''', (current_time, expires_at, agent_id))

            return cursor.rowcount > 0

    def get_key(self, agent_id: str) -> Optional[str]:
        """Get the current valid public key for an agent."""
        current_time = int(time.time())

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT public_key FROM agent_keys
                WHERE agent_id = ? AND is_revoked = 0 AND expires_at > ?
            ''', (agent_id, current_time))

            row = cursor.fetchone()
            return row[0] if row else None

    def rotate_key(self, agent_id: str, new_public_key_pem: str,
                   signature: str, ttl: int = DEFAULT_TTL) -> bool:
        """Rotate to a new key with signature verification."""
        current_time = int(time.time())

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Get current key
            cursor.execute('''
                SELECT public_key, rotation_count FROM agent_keys
                WHERE agent_id = ? AND is_revoked = 0
            ''', (agent_id,))

            current_row = cursor.fetchone()
            if not current_row:
                return False

            old_key_pem, rotation_count = current_row

            # Verify signature of new key with old key
            if not self._verify_rotation_signature(old_key_pem,
                                                   new_public_key_pem, signature):
                return False

            # Log the rotation
            old_hash = self._key_hash(old_key_pem)
            new_hash = self._key_hash(new_public_key_pem)

            cursor.execute('''
                INSERT INTO key_rotation_log
                (agent_id, old_key_hash, new_key_hash, rotated_at, signature)
                VALUES (?, ?, ?, ?, ?)
            ''', (agent_id, old_hash, new_hash, current_time, signature))

            # Update the key
            expires_at = current_time + ttl
            cursor.execute('''
                UPDATE agent_keys
                SET public_key = ?, last_seen = ?, expires_at = ?,
                    rotation_count = rotation_count + 1
                WHERE agent_id = ?
            ''', (new_public_key_pem, current_time, expires_at, agent_id))

            conn.commit()
            return True

    def _verify_rotation_signature(self, old_key_pem: str,
                                   new_key_pem: str, signature: str) -> bool:
        """Verify that the new key is signed by the old key."""
        try:
            old_key = serialization.load_pem_public_key(old_key_pem.encode())
            sig_bytes = bytes.fromhex(signature)
            message = f"rotate:{new_key_pem}".encode()

            old_key.verify(
                sig_bytes,
                message,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            return True
        except (InvalidSignature, Exception):
            return False

    def revoke_key(self, agent_id: str, reason: str = None) -> bool:
        """Revoke a key for an agent."""
        current_time = int(time.time())
        metadata = {'revocation_reason': reason} if reason else {}

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE agent_keys
                SET is_revoked = 1, revoked_at = ?, metadata = ?
                WHERE agent_id = ? AND is_revoked = 0
            ''', (current_time, json.dumps(metadata), agent_id))

            return cursor.rowcount > 0

    def cleanup_expired(self) -> int:
        """Remove expired keys and return count of cleaned up keys."""
        current_time = int(time.time())

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                'DELETE FROM agent_keys WHERE expires_at < ? AND is_revoked = 0',
                (current_time,)
            )
            return cursor.rowcount

    def list_keys(self, include_revoked: bool = False) -> List[Dict]:
        """List all keys with their metadata."""
        current_time = int(time.time())

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            query = '''
                SELECT agent_id, public_key, first_seen, last_seen,
                       expires_at, rotation_count, is_revoked, revoked_at, metadata
                FROM agent_keys
            '''

            if not include_revoked:
                query += ' WHERE is_revoked = 0'

            cursor.execute(query)

            keys = []
            for row in cursor.fetchall():
                agent_id, pub_key, first_seen, last_seen, expires_at, \
                rotation_count, is_revoked, revoked_at, metadata_json = row

                is_expired = expires_at < current_time
                key_hash = self._key_hash(pub_key)

                try:
                    metadata = json.loads(metadata_json) if metadata_json else {}
                except json.JSONDecodeError:
                    metadata = {}

                keys.append({
                    'agent_id': agent_id,
                    'key_hash': key_hash,
                    'first_seen': first_seen,
                    'last_seen': last_seen,
                    'expires_at': expires_at,
                    'is_expired': is_expired,
                    'rotation_count': rotation_count,
                    'is_revoked': bool(is_revoked),
                    'revoked_at': revoked_at,
                    'metadata': metadata
                })

            return keys

    def get_rotation_history(self, agent_id: str) -> List[Dict]:
        """Get rotation history for an agent."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT old_key_hash, new_key_hash, rotated_at, signature
                FROM key_rotation_log
                WHERE agent_id = ?
                ORDER BY rotated_at DESC
            ''', (agent_id,))

            history = []
            for row in cursor.fetchall():
                old_hash, new_hash, rotated_at, signature = row
                history.append({
                    'old_key_hash': old_hash,
                    'new_key_hash': new_hash,
                    'rotated_at': rotated_at,
                    'signature': signature
                })

            return history
