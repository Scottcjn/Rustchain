"""SQLite database operations for SophiaCore Attestation Inspector."""
import sqlite3
import os
from datetime import datetime
from typing import Optional, List, Dict, Any


DB_PATH = os.path.join(os.path.dirname(__file__), "sophia_inspections.db")


def get_connection() -> sqlite3.Connection:
    """Get a database connection with row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create the sophia_inspections table if it doesn't exist."""
    conn = get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sophia_inspections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                miner_id TEXT NOT NULL,
                verdict TEXT NOT NULL,
                confidence REAL NOT NULL,
                reasoning TEXT,
                signature TEXT,
                fingerprint_data TEXT,
                test_mode INTEGER DEFAULT 0,
                inspected_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_miner_id ON sophia_inspections(miner_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_inspected_at ON sophia_inspections(inspected_at)
        """)
        conn.commit()
    finally:
        conn.close()


def save_inspection(
    miner_id: str,
    verdict: str,
    confidence: float,
    reasoning: str,
    signature: Optional[str] = None,
    fingerprint_data: Optional[str] = None,
    test_mode: bool = False,
) -> int:
    """Save an inspection record and return its ID."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT INTO sophia_inspections
            (miner_id, verdict, confidence, reasoning, signature, fingerprint_data, test_mode, inspected_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                miner_id,
                verdict,
                confidence,
                reasoning,
                signature,
                fingerprint_data,
                1 if test_mode else 0,
                datetime.utcnow().isoformat(),
            ),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_latest_verdict(miner_id: str) -> Optional[Dict[str, Any]]:
    """Get the most recent inspection verdict for a miner."""
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT * FROM sophia_inspections
            WHERE miner_id = ?
            ORDER BY inspected_at DESC
            LIMIT 1
            """,
            (miner_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_history(miner_id: str, limit: int = 30) -> List[Dict[str, Any]]:
    """Get inspection history for a miner."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT * FROM sophia_inspections
            WHERE miner_id = ?
            ORDER BY inspected_at DESC
            LIMIT ?
            """,
            (miner_id, limit),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_queue(status: str = None) -> List[Dict[str, Any]]:
    """Get miners pending review: CAUTIOUS or SUSPICIOUS verdicts."""
    conn = get_connection()
    try:
        query = """
            SELECT miner_id, verdict, confidence, reasoning, inspected_at,
                   MAX(inspected_at) as latest_at
            FROM sophia_inspections
            WHERE verdict IN ('CAUTIOUS', 'SUSPICIOUS')
        """
        if status:
            query += " AND verdict = ? GROUP BY miner_id ORDER BY latest_at DESC"
            rows = conn.execute(query, (status,)).fetchall()
        else:
            query += " GROUP BY miner_id ORDER BY latest_at DESC"
            rows = conn.execute(query).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def override_verdict(
    miner_id: str,
    new_verdict: str,
    reason: str,
    admin_key: str,
) -> bool:
    """Override a miner's latest verdict. Returns True if successful."""
    # Simple admin key check (in production, use proper auth)
    if admin_key != "SOPHIA_ADMIN_KEY":
        return False

    conn = get_connection()
    try:
        # Save override as new inspection
        save_inspection(
            miner_id=miner_id,
            verdict=new_verdict,
            confidence=1.0,
            reasoning=f"OVERRIDE: {reason}",
            signature="ADMIN_OVERRIDE",
            test_mode=False,
        )
        return True
    finally:
        conn.close()


def get_all_miner_ids() -> List[str]:
    """Get all unique miner IDs from the database."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT DISTINCT miner_id FROM sophia_inspections"
        ).fetchall()
        return [row["miner_id"] for row in rows]
    finally:
        conn.close()


# Initialize DB on module load
init_db()
