// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import sqlite3
import time
import json
import logging
from typing import Optional, Dict, List, Tuple, Any
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from cryptography.exceptions import InvalidSignature

logger = logging.getLogger(__name__)

class BeaconIdentityService:
    def __init__(self, db_path: str = "beacon_identity.db", key_ttl_days: int = 30):
        self.db_path = db_path
        self.key_ttl_seconds = key_ttl_days * 24 * 3600
        self._init_database()

    def _init_database(self):
        """Initialize the identity database schema"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS agent_keys (
                    agent_id TEXT PRIMARY KEY,
                    public_key_pem TEXT NOT NULL,
                    first_seen INTEGER NOT NULL,
                    last_seen INTEGER NOT NULL,
                    rotation_count INTEGER DEFAULT 0,
                    is_revoked INTEGER DEFAULT 0,
                    revoked_at INTEGER,
                    metadata TEXT DEFAULT '{}'
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS key_rotations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT NOT NULL,
                    old_key_pem TEXT NOT NULL,
                    new_key_pem TEXT NOT NULL,
                    rotation_signature TEXT NOT NULL,
                    timestamp INTEGER NOT NULL,
                    FOREIGN KEY (agent_id) REFERENCES agent_keys (agent_id)
                )
            ''')

            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_agent_keys_last_seen
                ON agent_keys (last_seen)
            ''')

            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_key_rotations_agent_id
                ON key_rotations (agent_id)
            ''')

            conn.commit()

    def learn_key_from_envelope(self, agent_id: str, envelope_data: Dict[str, Any]) -> bool:
        """
        Learn a public key from an envelope using TOFU logic.
        Returns True if key was learned/updated, False if rejected.
        """
        try:
            public_key_pem = envelope_data.get('public_key')
            if not public_key_pem:
                logger.warning(f"No public key in envelope from {agent_id}")
                return False

            # Validate the public key format
            try:
                public_key = serialization.load_pem_public_key(public_key_pem.encode())
                if not isinstance(public_key, RSAPublicKey):
                    logger.warning(f"Unsupported key type from {agent_id}")
                    return False
            except Exception as e:
                logger.warning(f"Invalid public key from {agent_id}: {e}")
                return False

            current_time = int(time.time())

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Check if we already know this agent
                cursor.execute('''
                    SELECT public_key_pem, is_revoked, last_seen, rotation_count
                    FROM agent_keys WHERE agent_id = ?
                ''', (agent_id,))

                existing_record = cursor.fetchone()

                if existing_record:
                    existing_key, is_revoked, last_seen, rotation_count = existing_record

                    # Don't accept keys for revoked agents
                    if is_revoked:
                        logger.warning(f"Key learning rejected for revoked agent {agent_id}")
                        return False

                    # Check if key has expired
                    if current_time - last_seen > self.key_ttl_seconds:
                        logger.info(f"Existing key for {agent_id} has expired, allowing new key")
                        cursor.execute('''
                            UPDATE agent_keys
                            SET public_key_pem = ?, last_seen = ?, first_seen = ?,
                                rotation_count = rotation_count + 1
                            WHERE agent_id = ?
                        ''', (public_key_pem, current_time, current_time, agent_id))
                        conn.commit()
                        return True

                    # Same key - update heartbeat
                    if existing_key == public_key_pem:
                        cursor.execute('''
                            UPDATE agent_keys SET last_seen = ? WHERE agent_id = ?
                        ''', (current_time, agent_id))
                        conn.commit()
                        return True

                    # Different key - reject (would need rotation signature)
                    logger.warning(f"Key mismatch for {agent_id} - rotation signature required")
                    return False

                else:
                    # TOFU: First time seeing this agent, learn the key
                    cursor.execute('''
                        INSERT INTO agent_keys
                        (agent_id, public_key_pem, first_seen, last_seen, rotation_count)
                        VALUES (?, ?, ?, ?, 0)
                    ''', (agent_id, public_key_pem, current_time, current_time))
                    conn.commit()
                    logger.info(f"Learned new key for agent {agent_id} via TOFU")
                    return True

        except Exception as e:
            logger.error(f"Error learning key from envelope for {agent_id}: {e}")
            return False

    def rotate_key(self, agent_id: str, new_key_pem: str, rotation_signature: str) -> bool:
        """
        Rotate an agent's key with cryptographic proof from the old key.
        The rotation_signature should be: sign(new_key_pem, old_private_key)
        """
        try:
            current_time = int(time.time())

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Get the current key
                cursor.execute('''
                    SELECT public_key_pem, is_revoked
                    FROM agent_keys WHERE agent_id = ?
                ''', (agent_id,))

                record = cursor.fetchone()
                if not record:
                    logger.warning(f"No existing key found for agent {agent_id}")
                    return False

                old_key_pem, is_revoked = record
                if is_revoked:
                    logger.warning(f"Cannot rotate key for revoked agent {agent_id}")
                    return False

                # Validate the new key format
                try:
                    new_public_key = serialization.load_pem_public_key(new_key_pem.encode())
                    if not isinstance(new_public_key, RSAPublicKey):
                        logger.warning(f"Invalid new key type for {agent_id}")
                        return False
                except Exception as e:
                    logger.warning(f"Invalid new key format for {agent_id}: {e}")
                    return False

                # Verify the rotation signature
                if not self._verify_rotation_signature(old_key_pem, new_key_pem, rotation_signature):
                    logger.warning(f"Invalid rotation signature for {agent_id}")
                    return False

                # Update the key
                cursor.execute('''
                    UPDATE agent_keys
                    SET public_key_pem = ?, last_seen = ?, rotation_count = rotation_count + 1
                    WHERE agent_id = ?
                ''', (new_key_pem, current_time, agent_id))

                # Record the rotation
                cursor.execute('''
                    INSERT INTO key_rotations
                    (agent_id, old_key_pem, new_key_pem, rotation_signature, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                ''', (agent_id, old_key_pem, new_key_pem, rotation_signature, current_time))

                conn.commit()
                logger.info(f"Successfully rotated key for agent {agent_id}")
                return True

        except Exception as e:
            logger.error(f"Error rotating key for {agent_id}: {e}")
            return False

    def _verify_rotation_signature(self, old_key_pem: str, new_key_pem: str, signature_b64: str) -> bool:
        """Verify that the rotation signature was created by the old key"""
        try:
            import base64
            from cryptography.hazmat.primitives.asymmetric import padding

            old_public_key = serialization.load_pem_public_key(old_key_pem.encode())
            signature_bytes = base64.b64decode(signature_b64)

            old_public_key.verify(
                signature_bytes,
                new_key_pem.encode(),
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            return True

        except (InvalidSignature, Exception) as e:
            logger.debug(f"Signature verification failed: {e}")
            return False

    def revoke_key(self, agent_id: str) -> bool:
        """Revoke an agent's key"""
        try:
            current_time = int(time.time())

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute('''
                    UPDATE agent_keys
                    SET is_revoked = 1, revoked_at = ?
                    WHERE agent_id = ? AND is_revoked = 0
                ''', (current_time, agent_id))

                if cursor.rowcount > 0:
                    conn.commit()
                    logger.info(f"Revoked key for agent {agent_id}")
                    return True
                else:
                    logger.warning(f"No active key found to revoke for agent {agent_id}")
                    return False

        except Exception as e:
            logger.error(f"Error revoking key for {agent_id}: {e}")
            return False

    def update_heartbeat(self, agent_id: str) -> bool:
        """Update the last seen timestamp for an agent"""
        try:
            current_time = int(time.time())

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute('''
                    UPDATE agent_keys
                    SET last_seen = ?
                    WHERE agent_id = ? AND is_revoked = 0
                ''', (current_time, agent_id))

                if cursor.rowcount > 0:
                    conn.commit()
                    return True
                else:
                    return False

        except Exception as e:
            logger.error(f"Error updating heartbeat for {agent_id}: {e}")
            return False

    def cleanup_expired_keys(self) -> int:
        """Remove expired keys and return count of cleaned up keys"""
        try:
            current_time = int(time.time())
            expiry_threshold = current_time - self.key_ttl_seconds

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Get expired keys for logging
                cursor.execute('''
                    SELECT agent_id FROM agent_keys
                    WHERE last_seen < ? AND is_revoked = 0
                ''', (expiry_threshold,))

                expired_agents = [row[0] for row in cursor.fetchall()]

                # Mark them as expired/revoked
                cursor.execute('''
                    UPDATE agent_keys
                    SET is_revoked = 1, revoked_at = ?
                    WHERE last_seen < ? AND is_revoked = 0
                ''', (current_time, expiry_threshold))

                count = cursor.rowcount
                conn.commit()

                if count > 0:
                    logger.info(f"Expired {count} keys: {expired_agents}")

                return count

        except Exception as e:
            logger.error(f"Error during key cleanup: {e}")
            return 0

    def get_agent_key(self, agent_id: str) -> Optional[str]:
        """Get the current public key for an agent"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT public_key_pem FROM agent_keys
                    WHERE agent_id = ? AND is_revoked = 0
                ''', (agent_id,))

                result = cursor.fetchone()
                return result[0] if result else None

        except Exception as e:
            logger.error(f"Error getting key for {agent_id}: {e}")
            return None

    def list_all_keys(self) -> List[Dict[str, Any]]:
        """List all keys with metadata"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT agent_id, public_key_pem, first_seen, last_seen,
                           rotation_count, is_revoked, revoked_at, metadata
                    FROM agent_keys ORDER BY agent_id
                ''')

                keys = []
                for row in cursor.fetchall():
                    agent_id, pub_key, first_seen, last_seen, rotation_count, is_revoked, revoked_at, metadata_json = row

                    try:
                        metadata = json.loads(metadata_json) if metadata_json else {}
                    except json.JSONDecodeError:
                        metadata = {}

                    # Calculate key status
                    current_time = int(time.time())
                    is_expired = (current_time - last_seen) > self.key_ttl_seconds

                    keys.append({
                        'agent_id': agent_id,
                        'public_key_pem': pub_key,
                        'first_seen': first_seen,
                        'last_seen': last_seen,
                        'rotation_count': rotation_count,
                        'is_revoked': bool(is_revoked),
                        'revoked_at': revoked_at,
                        'is_expired': is_expired,
                        'metadata': metadata
                    })

                return keys

        except Exception as e:
            logger.error(f"Error listing keys: {e}")
            return []

    def get_rotation_history(self, agent_id: str) -> List[Dict[str, Any]]:
        """Get the key rotation history for an agent"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT old_key_pem, new_key_pem, rotation_signature, timestamp
                    FROM key_rotations
                    WHERE agent_id = ?
                    ORDER BY timestamp DESC
                ''', (agent_id,))

                rotations = []
                for row in cursor.fetchall():
                    old_key, new_key, signature, timestamp = row
                    rotations.append({
                        'old_key_pem': old_key,
                        'new_key_pem': new_key,
                        'rotation_signature': signature,
                        'timestamp': timestamp
                    })

                return rotations

        except Exception as e:
            logger.error(f"Error getting rotation history for {agent_id}: {e}")
            return []
