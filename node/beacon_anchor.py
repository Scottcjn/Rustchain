#!/usr/bin/env python3
"""
Beacon Anchor - Store and digest OpenClaw beacon envelopes for Ergo anchoring.

Beacon envelopes (hello, heartbeat, want, bounty, mayday, accord, pushback)
are stored in rustchain_v2.db and periodically committed to Ergo via the
existing ergo_miner_anchor.py system.
"""

import hashlib
import json
import sqlite3
import time
from hashlib import blake2b

try:
    from nacl.exceptions import BadSignatureError
    from nacl.signing import VerifyKey

    NACL_AVAILABLE = True
except ImportError:
    VerifyKey = None
    BadSignatureError = Exception
    NACL_AVAILABLE = False

DB_PATH = "/root/rustchain/rustchain_v2.db"

VALID_KINDS = {"hello", "heartbeat", "want", "bounty", "mayday", "accord", "pushback"}
REQUIRED_ENVELOPE_FIELDS = ("agent_id", "kind", "nonce", "sig", "pubkey")
UNSIGNED_TRANSPORT_FIELDS = ("sig", "_beacon_version")
LEGACY_PAYLOAD_HASH_VERSION = 1
CURRENT_PAYLOAD_HASH_VERSION = 2


def _agent_id_from_pubkey(pubkey_bytes: bytes) -> str:
    """Derive the canonical Beacon agent id from an Ed25519 public key."""
    return f"bcn_{hashlib.sha256(pubkey_bytes).hexdigest()[:12]}"


def _canonical_signed_fields(envelope: dict) -> dict:
    """Return the exact Beacon v2 body covered by signature verification and payload hashing."""
    return {field: value for field, value in envelope.items() if field not in UNSIGNED_TRANSPORT_FIELDS}


def _canonical_signing_payload(envelope: dict) -> bytes:
    """Return the canonical Beacon signing payload for the explicit signed field set."""
    return json.dumps(
        _canonical_signed_fields(envelope),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _ensure_payload_hash_version_column(conn: sqlite3.Connection):
    """
    Preserve existing hashes as legacy version 1 and mark new hashes as version 2.

    The table only stores the derived payload hash, not the original envelope body,
    so pre-upgrade rows cannot be recomputed safely in place. We therefore tag them
    as legacy and let new writes opt into the explicit signed-field hash contract.
    """
    columns = {row[1] for row in conn.execute("PRAGMA table_info(beacon_envelopes)").fetchall()}
    if "payload_hash_version" not in columns:
        conn.execute("ALTER TABLE beacon_envelopes ADD COLUMN payload_hash_version INTEGER NOT NULL DEFAULT 1")
    conn.execute(
        "UPDATE beacon_envelopes SET payload_hash_version = ? WHERE payload_hash_version IS NULL",
        (LEGACY_PAYLOAD_HASH_VERSION,),
    )


def verify_envelope_signature(envelope: dict) -> tuple[bool, str]:
    """
    Verify an HTTP-submitted Beacon envelope.

    Beacon v2 envelopes are signed with Ed25519 over the canonical JSON body
    excluding the `sig` field. The claimed `agent_id` must also match the
    submitted public key to prevent identity spoofing.
    """
    sig_hex = envelope.get("sig", "")
    pubkey_hex = envelope.get("pubkey", "")
    agent_id = envelope.get("agent_id", "")

    if not all([sig_hex, pubkey_hex, agent_id]):
        return False, "missing_signature_fields"

    try:
        pubkey_bytes = bytes.fromhex(pubkey_hex)
        signature_bytes = bytes.fromhex(sig_hex)
    except ValueError:
        return False, "invalid_signature_or_pubkey_encoding"

    expected_agent_id = _agent_id_from_pubkey(pubkey_bytes)
    if agent_id != expected_agent_id:
        return False, "agent_id_pubkey_mismatch"

    if not NACL_AVAILABLE:
        return False, "signature_verification_unavailable"

    try:
        verify_key = VerifyKey(pubkey_bytes)
        verify_key.verify(_canonical_signing_payload(envelope), signature_bytes)
        return True, ""
    except (BadSignatureError, Exception):
        return False, "invalid_signature"


def init_beacon_table(db_path=DB_PATH):
    """Create beacon_envelopes table if it doesn't exist."""
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS beacon_envelopes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                nonce TEXT UNIQUE NOT NULL,
                sig TEXT NOT NULL,
                pubkey TEXT NOT NULL,
                payload_hash TEXT NOT NULL,
                payload_hash_version INTEGER NOT NULL DEFAULT 1,
                anchored INTEGER DEFAULT 0,
                created_at INTEGER NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_beacon_anchored
            ON beacon_envelopes(anchored)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_beacon_agent
            ON beacon_envelopes(agent_id, created_at)
        """)
        _ensure_payload_hash_version_column(conn)
        conn.commit()


def hash_envelope(envelope: dict) -> str:
    """Compute the version-2 blake2b hash over the explicit signed field set."""
    return blake2b(_canonical_signing_payload(envelope), digest_size=32).hexdigest()


def store_envelope(envelope: dict, db_path=DB_PATH) -> dict:
    """
    Store a beacon envelope. Returns {"ok": True, "id": <row_id>} or error dict.
    Expects envelope to have: agent_id, kind, nonce, sig, pubkey
    """
    agent_id = envelope.get("agent_id", "")
    kind = envelope.get("kind", "")
    nonce = envelope.get("nonce", "")
    sig = envelope.get("sig", "")
    pubkey = envelope.get("pubkey", "")

    if not all(envelope.get(field, "") for field in REQUIRED_ENVELOPE_FIELDS):
        return {"ok": False, "error": "missing_fields"}

    if kind not in VALID_KINDS:
        return {"ok": False, "error": f"invalid_kind:{kind}"}

    sig_ok, sig_err = verify_envelope_signature(envelope)
    if not sig_ok:
        return {"ok": False, "error": sig_err}

    payload_hash = hash_envelope(envelope)
    now = int(time.time())

    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "INSERT INTO beacon_envelopes "
                "(agent_id, kind, nonce, sig, pubkey, payload_hash, payload_hash_version, anchored, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)",
                (
                    agent_id,
                    kind,
                    nonce,
                    sig,
                    pubkey,
                    payload_hash,
                    CURRENT_PAYLOAD_HASH_VERSION,
                    now,
                ),
            )
            conn.commit()
            row_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        return {
            "ok": True,
            "id": row_id,
            "payload_hash": payload_hash,
            "payload_hash_version": CURRENT_PAYLOAD_HASH_VERSION,
        }
    except sqlite3.IntegrityError:
        return {"ok": False, "error": "duplicate_nonce"}


def compute_beacon_digest(db_path=DB_PATH) -> dict:
    """
    Compute a blake2b digest of all un-anchored beacon envelopes.
    Returns {"digest": hex, "count": N, "ids": [...], "latest_ts": T}
    or {"digest": None, "count": 0} if no pending envelopes.

    During the transition from legacy payload hashes to explicit signed-field
    hashes, the digest preserves the original payload-hash concatenation and
    reports whether multiple hash versions are still pending.
    """
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT id, payload_hash, payload_hash_version, created_at FROM beacon_envelopes "
            "WHERE anchored = 0 ORDER BY id ASC"
        ).fetchall()

    if not rows:
        return {
            "digest": None,
            "count": 0,
            "ids": [],
            "latest_ts": 0,
            "payload_hash_versions": [],
            "mixed_payload_hash_versions": False,
        }

    ids = [r[0] for r in rows]
    # Preserve the historic digest input for pending rows so a rollout does not
    # retroactively change the digest of an unchanged legacy-only backlog.
    hashes = [r[1] for r in rows]
    versions = sorted({r[2] for r in rows})
    latest_ts = max(r[3] for r in rows)

    # Concatenate all payload hashes and compute digest
    combined = "|".join(hashes).encode()
    digest = blake2b(combined, digest_size=32).hexdigest()

    return {
        "digest": digest,
        "count": len(rows),
        "ids": ids,
        "latest_ts": latest_ts,
        "payload_hash_versions": versions,
        "mixed_payload_hash_versions": len(versions) > 1,
    }


def mark_anchored(envelope_ids: list, db_path=DB_PATH):
    """Set anchored=1 for the given envelope IDs."""
    if not envelope_ids:
        return
    with sqlite3.connect(db_path) as conn:
        placeholders = ",".join("?" for _ in envelope_ids)
        conn.execute(f"UPDATE beacon_envelopes SET anchored = 1 WHERE id IN ({placeholders})", envelope_ids)
        conn.commit()


def get_recent_envelopes(limit=50, offset=0, db_path=DB_PATH) -> list:
    """Return recent envelopes, newest first."""
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, agent_id, kind, nonce, payload_hash, payload_hash_version, anchored, created_at "
            "FROM beacon_envelopes ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    return [dict(r) for r in rows]


if __name__ == "__main__":
    init_beacon_table()
    print("[beacon_anchor] Table initialized.")

    # Demo: compute digest
    d = compute_beacon_digest()
    print(f"[beacon_anchor] Pending: {d['count']} envelopes")
    if d["digest"]:
        print(f"[beacon_anchor] Digest: {d['digest'][:32]}...")
