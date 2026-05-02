"""
Beacon Agent Identity — TOFU Key Management with TTL, Rotation, and Revocation.

Implements Trust-On-First-Use (TOFU) key learning for beacon agents with:
  - TTL-based key expiration (30 days without heartbeat)
  - Key rotation: new keys signed by the old key
  - Revocation: permanently block a key
  - Key metadata: first_seen, last_seen, rotation_count
  - Persistence via SQLite (reuses rustchain_v2.db)

Closes: Scottcjn/rustchain-bounties#392
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger("beacon.identity")

# Default key TTL: 30 days in seconds
DEFAULT_KEY_TTL: int = int(os.environ.get("BEACON_KEY_TTL", str(30 * 24 * 60 * 60)))

DB_PATH: str = os.environ.get("BEACON_DB_PATH", "/root/rustchain/rustchain_v2.db")

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

    _CRYPTO_AVAILABLE = True
except ImportError:  # pragma: no cover
    _CRYPTO_AVAILABLE = False


# ---------------------------------------------------------------------------
# Database schema
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS beacon_known_keys (
    agent_id        TEXT PRIMARY KEY,
    pubkey_hex      TEXT NOT NULL,
    first_seen      REAL NOT NULL,
    last_seen       REAL NOT NULL,
    rotation_count  INTEGER NOT NULL DEFAULT 0,
    previous_key    TEXT,
    revoked         INTEGER NOT NULL DEFAULT 0,
    revoked_at      REAL,
    revoked_reason  TEXT
);
CREATE INDEX IF NOT EXISTS idx_bkk_revoked   ON beacon_known_keys(revoked);
CREATE INDEX IF NOT EXISTS idx_bkk_last_seen ON beacon_known_keys(last_seen);

CREATE TABLE IF NOT EXISTS beacon_key_rotation_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id        TEXT NOT NULL,
    old_pubkey_hex  TEXT NOT NULL,
    new_pubkey_hex  TEXT NOT NULL,
    rotated_at      REAL NOT NULL,
    rotation_num    INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_bkrl_agent ON beacon_key_rotation_log(agent_id);
"""


def init_identity_tables(db_path: str = DB_PATH) -> None:
    """Create beacon_known_keys and rotation log tables if they don't exist."""
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA_SQL)
        conn.commit()


# ---------------------------------------------------------------------------
# Agent ID derivation (matches beacon_anchor.py convention)
# ---------------------------------------------------------------------------

def agent_id_from_pubkey(pubkey_bytes: bytes) -> str:
    """
    Derive canonical Beacon agent ID from public key.
    
    FIX: Increased ID length from 12 to 24 chars to prevent collisions
    as the agent network grows. (12 hex chars = 48 bits, too small for global scale).
    """
    return "bcn_" + hashlib.sha256(pubkey_bytes).hexdigest()[:24]


# ---------------------------------------------------------------------------
# Ed25519 signature verification
# ---------------------------------------------------------------------------

def _verify_ed25519(pubkey_hex: str, signature_hex: str, message: bytes) -> bool:
    """Verify an Ed25519 signature.  Returns False if cryptography is not installed."""
    if not _CRYPTO_AVAILABLE:
        log.warning("cryptography package not available — signature verification skipped")
        return False
    try:
        pk = Ed25519PublicKey.from_public_bytes(bytes.fromhex(pubkey_hex))
        pk.verify(bytes.fromhex(signature_hex), message)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Core key-store operations
# ---------------------------------------------------------------------------

def load_key(agent_id: str, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    """Fetch a single key record by agent_id, or None."""
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM beacon_known_keys WHERE agent_id = ?", (agent_id,)
        ).fetchone()
    return dict(row) if row else None


def load_all_keys(db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    """Return all key records."""
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM beacon_known_keys ORDER BY first_seen ASC"
        ).fetchall()
    return [dict(r) for r in rows]


def _upsert_key(rec: Dict[str, Any], db_path: str = DB_PATH) -> None:
    """Insert or replace a key record."""
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO beacon_known_keys
                (agent_id, pubkey_hex, first_seen, last_seen, rotation_count,
                 previous_key, revoked, revoked_at, revoked_reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(agent_id) DO UPDATE SET
                pubkey_hex     = excluded.pubkey_hex,
                first_seen     = CASE WHEN first_seen < excluded.first_seen
                                      THEN first_seen ELSE excluded.first_seen END,
                last_seen      = excluded.last_seen,
                rotation_count = excluded.rotation_count,
                previous_key   = excluded.previous_key,
                revoked        = excluded.revoked,
                revoked_at     = excluded.revoked_at,
                revoked_reason = excluded.revoked_reason
            """,
            (
                rec["agent_id"],
                rec["pubkey_hex"],
                rec["first_seen"],
                rec["last_seen"],
                rec.get("rotation_count", 0),
                rec.get("previous_key"),
                int(rec.get("revoked", False)),
                rec.get("revoked_at"),
                rec.get("revoked_reason"),
            ),
        )
        conn.commit()


# ---------------------------------------------------------------------------
# TOFU: learn key from an incoming envelope
# ---------------------------------------------------------------------------

def learn_key_from_envelope(
    envelope: Dict[str, Any], db_path: str = DB_PATH
) -> Tuple[bool, str]:
    """
    Trust-On-First-Use key learning.

    - First envelope from an agent → store pubkey + metadata.
    - Subsequent envelopes → update last_seen timestamp.
    - Revoked agents → reject (returns False).

    Returns (accepted: bool, reason: str).
    """
    agent_id = envelope.get("agent_id", "")
    pubkey_hex = envelope.get("pubkey", "")

    if not agent_id or not pubkey_hex:
        return False, "missing_agent_id_or_pubkey"

    # Verify agent_id is consistent with declared pubkey
    try:
        expected_id = agent_id_from_pubkey(bytes.fromhex(pubkey_hex))
    except ValueError:
        return False, "invalid_pubkey_encoding"

    if expected_id != agent_id:
        return False, "agent_id_pubkey_mismatch"

    init_identity_tables(db_path)

    existing = load_key(agent_id, db_path)

    if existing:
        if existing["revoked"]:
            return False, "key_revoked"

        # Key already known — update last_seen
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "UPDATE beacon_known_keys SET last_seen = ? WHERE agent_id = ?",
                (time.time(), agent_id),
            )
            conn.commit()
        return True, "key_updated"

    # New agent — learn key (TOFU)
    now = time.time()
    _upsert_key(
        {
            "agent_id": agent_id,
            "pubkey_hex": pubkey_hex,
            "first_seen": now,
            "last_seen": now,
            "rotation_count": 0,
            "previous_key": None,
            "revoked": False,
            "revoked_at": None,
            "revoked_reason": None,
        },
        db_path,
    )
    log.info("TOFU: learned new key for %s", agent_id)
    return True, "key_learned"


# ---------------------------------------------------------------------------
# TTL / expiration
# ---------------------------------------------------------------------------

def is_key_expired(agent_id: str, ttl: int = DEFAULT_KEY_TTL, db_path: str = DB_PATH) -> bool:
    """Return True if the key has not been seen within *ttl* seconds."""
    rec = load_key(agent_id, db_path)
    if rec is None:
        return True  # unknown → treat as expired
    if rec["revoked"]:
        return True
    return (time.time() - rec["last_seen"]) > ttl


def expire_old_keys(
    ttl: int = DEFAULT_KEY_TTL, dry_run: bool = True, db_path: str = DB_PATH
) -> List[str]:
    """Return (and optionally delete) keys that have exceeded *ttl* without a heartbeat."""
    cutoff = time.time() - ttl
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT agent_id FROM beacon_known_keys WHERE last_seen < ? AND revoked = 0",
            (cutoff,),
        ).fetchall()
        expired_ids = [r[0] for r in rows]
        if not dry_run and expired_ids:
            placeholders = ",".join("?" for _ in expired_ids)
            conn.execute(
                f"DELETE FROM beacon_known_keys WHERE agent_id IN ({placeholders})",
                expired_ids,
            )
            conn.commit()
    return expired_ids


# ---------------------------------------------------------------------------
# Revocation
# ---------------------------------------------------------------------------

def revoke_key(
    agent_id: str, reason: Optional[str] = None, db_path: str = DB_PATH
) -> Tuple[bool, str]:
    """
    Permanently revoke a known key.

    Returns (success, message).
    """
    init_identity_tables(db_path)
    rec = load_key(agent_id, db_path)
    if rec is None:
        return False, f"agent {agent_id!r} not found"
    if rec["revoked"]:
        return False, f"agent {agent_id!r} is already revoked"

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """UPDATE beacon_known_keys
               SET revoked = 1, revoked_at = ?, revoked_reason = ?
               WHERE agent_id = ?""",
            (time.time(), reason or "manual_revocation", agent_id),
        )
        conn.commit()
    log.info("Revoked key for agent %s: %s", agent_id, reason)
    return True, f"key revoked for {agent_id}"


# ---------------------------------------------------------------------------
# Key rotation
# ---------------------------------------------------------------------------

def rotate_key(
    agent_id: str,
    new_pubkey_hex: str,
    signature_hex: str,
    db_path: str = DB_PATH,
) -> Tuple[bool, str]:
    """
    Rotate an agent's public key.

    The caller must provide *signature_hex* which is the Ed25519 signature of
    the canonical rotation payload::

        b"rotate:<agent_id>:<new_pubkey_hex>"

    signed with the **old** private key.  This proves possession of the
    old private key and authorises the rotation.

    Returns (success, message).
    """
    init_identity_tables(db_path)
    rec = load_key(agent_id, db_path)

    if rec is None:
        return False, f"agent {agent_id!r} not found in known keys"
    if rec["revoked"]:
        return False, f"agent {agent_id!r} key is revoked — cannot rotate"

    # Canonical payload that was signed
    payload = f"rotate:{agent_id}:{new_pubkey_hex}".encode()

    if not _verify_ed25519(rec["pubkey_hex"], signature_hex, payload):
        return False, "invalid signature: rotation not authorised by old key"

    now = time.time()
    new_rotation_count = rec["rotation_count"] + 1
    old_pubkey = rec["pubkey_hex"]

    # Update the key record
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """UPDATE beacon_known_keys
               SET pubkey_hex = ?, last_seen = ?, rotation_count = ?,
                   previous_key = ?, revoked = 0, revoked_at = NULL, revoked_reason = NULL
               WHERE agent_id = ?""",
            (new_pubkey_hex, now, new_rotation_count, old_pubkey, agent_id),
        )
        # Log the rotation
        conn.execute(
            """INSERT INTO beacon_key_rotation_log
               (agent_id, old_pubkey_hex, new_pubkey_hex, rotated_at, rotation_num)
               VALUES (?, ?, ?, ?, ?)""",
            (agent_id, old_pubkey, new_pubkey_hex, now, new_rotation_count),
        )
        conn.commit()

    log.info("Key rotated for %s (rotation #%d)", agent_id, new_rotation_count)
    return True, f"key rotated for {agent_id} (rotation #{new_rotation_count})"


# ---------------------------------------------------------------------------
# Listing / info
# ---------------------------------------------------------------------------

def list_keys(
    include_revoked: bool = True,
    include_expired: bool = True,
    ttl: int = DEFAULT_KEY_TTL,
    db_path: str = DB_PATH,
) -> List[Dict[str, Any]]:
    """Return enriched key records for display."""
    init_identity_tables(db_path)
    recs = load_all_keys(db_path)
    now = time.time()
    results = []

    for rec in recs:
        is_revoked = bool(rec["revoked"])
        is_expired = not is_revoked and (now - rec["last_seen"]) > ttl

        if not include_revoked and is_revoked:
            continue
        if not include_expired and is_expired:
            continue

        results.append(
            {
                "agent_id": rec["agent_id"],
                "pubkey_hex": rec["pubkey_hex"],
                "first_seen": datetime.fromtimestamp(rec["first_seen"], tz=timezone.utc).isoformat(),
                "last_seen": datetime.fromtimestamp(rec["last_seen"], tz=timezone.utc).isoformat(),
                "rotation_count": rec["rotation_count"],
                "previous_key": rec.get("previous_key"),
                "is_revoked": is_revoked,
                "revoked_reason": rec.get("revoked_reason"),
                "is_expired": is_expired,
                "age_days": int((now - rec["first_seen"]) / 86_400),
            }
        )

    return results


def get_key_info(agent_id: str, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    """Return enriched info for a single agent key, or None."""
    init_identity_tables(db_path)
    rec = load_key(agent_id, db_path)
    if rec is None:
        return None

    now = time.time()
    is_revoked = bool(rec["revoked"])
    is_expired = not is_revoked and (now - rec["last_seen"]) > DEFAULT_KEY_TTL

    return {
        "agent_id": rec["agent_id"],
        "pubkey_hex": rec["pubkey_hex"],
        "first_seen": datetime.fromtimestamp(rec["first_seen"], tz=timezone.utc).isoformat(),
        "last_seen": datetime.fromtimestamp(rec["last_seen"], tz=timezone.utc).isoformat(),
        "rotation_count": rec["rotation_count"],
        "previous_key": rec.get("previous_key"),
        "is_revoked": is_revoked,
        "revoked_at": (
            datetime.fromtimestamp(rec["revoked_at"], tz=timezone.utc).isoformat()
            if rec.get("revoked_at") else None
        ),
        "revoked_reason": rec.get("revoked_reason"),
        "is_expired": is_expired,
        "age_days": int((now - rec["first_seen"]) / 86_400),
    }
