from __future__ import annotations

import secrets
import sqlite3
import time
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class Challenge:
    nonce: str
    expires_at: int


def ensure_tables(conn: sqlite3.Connection) -> None:
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS used_nonces (
            miner_id TEXT NOT NULL,
            nonce TEXT NOT NULL,
            used_at INTEGER NOT NULL,
            expires_at INTEGER NOT NULL,
            PRIMARY KEY (miner_id, nonce)
        )
        """
    )
    c.execute("CREATE INDEX IF NOT EXISTS idx_used_nonces_expires ON used_nonces(expires_at)")
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS attest_challenges (
            nonce TEXT PRIMARY KEY,
            issued_at INTEGER NOT NULL,
            expires_at INTEGER NOT NULL
        )
        """
    )
    c.execute("CREATE INDEX IF NOT EXISTS idx_attest_challenges_expires ON attest_challenges(expires_at)")
    conn.commit()


def cleanup_expired(conn: sqlite3.Connection, now_ts: Optional[int] = None) -> None:
    now = int(now_ts or time.time())
    c = conn.cursor()
    c.execute("DELETE FROM used_nonces WHERE expires_at < ?", (now,))
    c.execute("DELETE FROM attest_challenges WHERE expires_at < ?", (now,))
    conn.commit()


def issue_challenge(conn: sqlite3.Connection, ttl_seconds: int = 120, now_ts: Optional[int] = None) -> Challenge:
    now = int(now_ts or time.time())
    expires_at = now + int(ttl_seconds)
    nonce = secrets.token_hex(32)
    c = conn.cursor()
    c.execute(
        "INSERT INTO attest_challenges (nonce, issued_at, expires_at) VALUES (?, ?, ?)",
        (nonce, now, expires_at),
    )
    conn.commit()
    return Challenge(nonce=nonce, expires_at=expires_at)


def consume_challenge(conn: sqlite3.Connection, nonce: str, now_ts: Optional[int] = None) -> bool:
    if not nonce:
        return False
    now = int(now_ts or time.time())
    c = conn.cursor()
    row = c.execute("SELECT expires_at FROM attest_challenges WHERE nonce = ?", (nonce,)).fetchone()
    if not row:
        return False
    expires_at = int(row[0])
    if expires_at < now:
        c.execute("DELETE FROM attest_challenges WHERE nonce = ?", (nonce,))
        conn.commit()
        return False
    c.execute("DELETE FROM attest_challenges WHERE nonce = ?", (nonce,))
    conn.commit()
    return True


def validate_nonce_freshness(nonce: str, now_ts: Optional[int] = None, skew_seconds: int = 60) -> Tuple[bool, str]:
    if not nonce:
        return False, "missing_nonce"
    if not str(nonce).isdigit():
        return False, "nonce_not_timestamp"
    now = int(now_ts or time.time())
    try:
        ts = int(str(nonce))
    except ValueError:
        return False, "nonce_not_timestamp"
    if abs(ts - now) > int(skew_seconds):
        return False, "nonce_out_of_window"
    return True, "ok"


def mark_nonce_used(
    conn: sqlite3.Connection,
    miner_id: str,
    nonce: str,
    ttl_seconds: int = 3600,
    now_ts: Optional[int] = None,
) -> Tuple[bool, str]:
    if not miner_id:
        return False, "missing_miner_id"
    if not nonce:
        return False, "missing_nonce"
    now = int(now_ts or time.time())
    expires_at = now + int(ttl_seconds)
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO used_nonces (miner_id, nonce, used_at, expires_at) VALUES (?, ?, ?, ?)",
            (miner_id, str(nonce), now, expires_at),
        )
        conn.commit()
        return True, "ok"
    except sqlite3.IntegrityError:
        return False, "replay_detected"
