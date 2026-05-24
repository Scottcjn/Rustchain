# SPDX-License-Identifier: MIT
"""Append-only audit event log for reconstructing RustChain state changes."""

import hashlib
import json
import sqlite3
import time
from typing import Optional


def ensure_audit_event_log(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            subject_type TEXT NOT NULL,
            subject_id TEXT NOT NULL,
            actor_id TEXT,
            epoch INTEGER,
            ts INTEGER NOT NULL,
            payload_json TEXT NOT NULL,
            payload_hash TEXT NOT NULL,
            previous_event_hash TEXT,
            event_hash TEXT NOT NULL UNIQUE
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_audit_events_subject
        ON audit_events(subject_type, subject_id, id)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_audit_events_type_epoch
        ON audit_events(event_type, epoch, id)
        """
    )


def _canonical_payload(payload: Optional[dict]) -> str:
    return json.dumps(payload or {}, sort_keys=True, separators=(",", ":"), default=str)


def append_audit_event(
    conn: sqlite3.Connection,
    *,
    event_type: str,
    subject_type: str,
    subject_id: str,
    actor_id: Optional[str] = None,
    epoch: Optional[int] = None,
    ts: Optional[int] = None,
    payload: Optional[dict] = None,
) -> dict:
    """Append one hash-chained audit event on the caller's SQLite connection."""
    if not event_type or not subject_type or not subject_id:
        raise ValueError("event_type, subject_type, and subject_id are required")

    ensure_audit_event_log(conn)
    ts = int(time.time()) if ts is None else int(ts)
    payload_json = _canonical_payload(payload)
    payload_hash = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
    previous_row = conn.execute(
        "SELECT event_hash FROM audit_events ORDER BY id DESC LIMIT 1"
    ).fetchone()
    previous_hash = previous_row[0] if previous_row else None
    event_material = _canonical_payload(
        {
            "event_type": event_type,
            "subject_type": subject_type,
            "subject_id": subject_id,
            "actor_id": actor_id,
            "epoch": epoch,
            "ts": ts,
            "payload_hash": payload_hash,
            "previous_event_hash": previous_hash,
        }
    )
    event_hash = hashlib.sha256(event_material.encode("utf-8")).hexdigest()
    cursor = conn.execute(
        """
        INSERT INTO audit_events (
            event_type, subject_type, subject_id, actor_id, epoch, ts,
            payload_json, payload_hash, previous_event_hash, event_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_type,
            subject_type,
            subject_id,
            actor_id,
            epoch,
            ts,
            payload_json,
            payload_hash,
            previous_hash,
            event_hash,
        ),
    )
    return {
        "id": cursor.lastrowid,
        "event_hash": event_hash,
        "previous_event_hash": previous_hash,
        "payload_hash": payload_hash,
    }


def append_audit_event_safely(conn: sqlite3.Connection, **kwargs) -> Optional[dict]:
    """Best-effort audit append for runtime paths that must not fail state writes."""
    try:
        return append_audit_event(conn, **kwargs)
    except Exception:
        return None
