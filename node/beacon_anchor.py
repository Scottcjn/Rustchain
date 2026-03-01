#!/usr/bin/env python3
"""
Beacon Anchor - Store and digest OpenClaw beacon envelopes for Ergo anchoring.

Beacon envelopes (hello, heartbeat, want, bounty, mayday, accord, pushback)
are stored in rustchain_v2.db and periodically committed to Ergo via the
existing ergo_miner_anchor.py system.
"""
import sqlite3, time, json
from hashlib import blake2b

DB_PATH = "/root/rustchain/rustchain_v2.db"

VALID_KINDS = {"hello", "heartbeat", "want", "bounty", "mayday", "accord", "pushback"}


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
        conn.commit()


def hash_envelope(envelope: dict) -> str:
    """Compute blake2b hash of the full envelope JSON (canonical, sorted keys)."""
    data = json.dumps(envelope, sort_keys=True, separators=(',', ':')).encode()
    return blake2b(data, digest_size=32).hexdigest()


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

    if not all([agent_id, kind, nonce, sig, pubkey]):
        return {"ok": False, "error": "missing_fields"}

    if kind not in VALID_KINDS:
        return {"ok": False, "error": f"invalid_kind:{kind}"}

    payload_hash = hash_envelope(envelope)
    now = int(time.time())

    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute("INSERT INTO beacon_envelopes "
                         "(agent_id, kind, nonce, sig, pubkey, payload_hash, anchored, created_at) "
                         "VALUES (?, ?, ?, ?, ?, ?, 0, ?)",
                         (agent_id, kind, nonce, sig, pubkey, payload_hash, now))
            conn.commit()
            row_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        return {"ok": True, "id": row_id, "payload_hash": payload_hash}
    except sqlite3.IntegrityError:
        return {"ok": False, "error": "duplicate_nonce"}


def compute_beacon_digest(db_path=DB_PATH) -> dict:
    """
    Compute a blake2b digest of all un-anchored beacon envelopes.
    Returns {"digest": hex, "count": N, "ids": [...], "latest_ts": T}
    or {"digest": None, "count": 0} if no pending envelopes.
    """
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT id, payload_hash, created_at FROM beacon_envelopes "
            "WHERE anchored = 0 ORDER BY id ASC"
        ).fetchall()

    if not rows:
        return {"digest": None, "count": 0, "ids": [], "latest_ts": 0}

    ids = [r[0] for r in rows]
    hashes = [r[1] for r in rows]
    latest_ts = max(r[2] for r in rows)

    # Concatenate all payload hashes and compute digest
    combined = "|".join(hashes).encode()
    digest = blake2b(combined, digest_size=32).hexdigest()

    return {
        "digest": digest,
        "count": len(rows),
        "ids": ids,
        "latest_ts": latest_ts
    }


def mark_anchored(envelope_ids: list, db_path=DB_PATH):
    """Set anchored=1 for the given envelope IDs."""
    if not envelope_ids:
        return
    with sqlite3.connect(db_path) as conn:
        placeholders = ",".join("?" for _ in envelope_ids)
        conn.execute(
            f"UPDATE beacon_envelopes SET anchored = 1 WHERE id IN ({placeholders})",
            envelope_ids
        )
        conn.commit()


def get_recent_envelopes(limit=50, offset=0, db_path=DB_PATH) -> list:
    """Return recent envelopes, newest first."""
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, agent_id, kind, nonce, payload_hash, anchored, created_at "
            "FROM beacon_envelopes ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset)
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
