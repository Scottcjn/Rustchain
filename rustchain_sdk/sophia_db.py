"""
sophia_db.py -- Raw sqlite3 database layer for SophiaCore Attestation Inspector.
RIP-306 implementation for Rustchain bounty #2261.

Tables:
  sophia_inspections  -- verdict records with confidence scores
  sophia_review_queue -- CAUTIOUS/SUSPICIOUS cases awaiting human review
"""

import sqlite3
import os
import time
import hashlib
import json

DB_PATH = os.environ.get("SOPHIA_DB_PATH", "sophia_inspections.db")


def get_connection(db_path=None):
    """Get a sqlite3 connection with row_factory set."""
    conn = sqlite3.connect(db_path or DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path=None):
    """Create tables if they don't exist. Idempotent."""
    conn = get_connection(db_path)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS sophia_inspections (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            miner_id         TEXT    NOT NULL,
            verdict          TEXT    NOT NULL,
            confidence       REAL    NOT NULL,
            reasoning        TEXT    NOT NULL DEFAULT '',
            fingerprint_hash TEXT    NOT NULL,
            inspected_at     REAL    NOT NULL,
            model_used       TEXT    NOT NULL DEFAULT 'rule-based',
            inspection_type  TEXT    NOT NULL DEFAULT 'on-demand'
        )
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_inspections_miner
        ON sophia_inspections(miner_id)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_inspections_time
        ON sophia_inspections(inspected_at DESC)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_inspections_verdict
        ON sophia_inspections(verdict)
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS sophia_review_queue (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            inspection_id   INTEGER NOT NULL,
            miner_id        TEXT    NOT NULL,
            verdict         TEXT    NOT NULL DEFAULT '',
            reviewed        INTEGER NOT NULL DEFAULT 0,
            reviewer        TEXT,
            reviewed_at     REAL,
            FOREIGN KEY (inspection_id) REFERENCES sophia_inspections(id)
        )
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_review_pending
        ON sophia_review_queue(reviewed)
    """)

    conn.commit()
    conn.close()


def fingerprint_hash(fingerprint_bundle):
    """Deterministic SHA-256 of a fingerprint dict."""
    canonical = json.dumps(fingerprint_bundle, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


# -- Inspection CRUD ------------------------------------------------------

def store_inspection(conn, miner_id, verdict, confidence, reasoning,
                     model_used, fingerprint_bundle,
                     inspection_type="on-demand"):
    """Insert an inspection record. Returns the row id."""
    fp_hash = fingerprint_hash(fingerprint_bundle)
    now = time.time()

    cur = conn.execute(
        """INSERT INTO sophia_inspections
           (miner_id, verdict, confidence, reasoning, model_used,
            inspected_at, fingerprint_hash, inspection_type)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (miner_id, verdict, confidence, reasoning, model_used,
         now, fp_hash, inspection_type)
    )
    conn.commit()
    return cur.lastrowid


def get_latest_inspection(conn, miner_id):
    """Get the most recent inspection for a miner."""
    row = conn.execute(
        """SELECT * FROM sophia_inspections
           WHERE miner_id = ?
           ORDER BY inspected_at DESC LIMIT 1""",
        (miner_id,)
    ).fetchone()
    return dict(row) if row else None


def get_miner_history(conn, miner_id, limit=10):
    """Get recent inspections for a specific miner."""
    rows = conn.execute(
        """SELECT * FROM sophia_inspections
           WHERE miner_id = ?
           ORDER BY inspected_at DESC LIMIT ?""",
        (miner_id, limit)
    ).fetchall()
    return [dict(r) for r in rows]


def get_inspection_history(conn, page=1, per_page=25):
    """Get paginated inspection history."""
    offset = (page - 1) * per_page
    rows = conn.execute(
        """SELECT * FROM sophia_inspections
           ORDER BY inspected_at DESC
           LIMIT ? OFFSET ?""",
        (per_page, offset)
    ).fetchall()

    total = conn.execute(
        "SELECT COUNT(*) FROM sophia_inspections"
    ).fetchone()[0]

    return {
        "inspections": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page
    }


# -- Review Queue CRUD ----------------------------------------------------

def enqueue_review(conn, inspection_id, miner_id, verdict=""):
    """Add an inspection to the human review queue."""
    conn.execute(
        """INSERT INTO sophia_review_queue
           (inspection_id, miner_id, verdict)
           VALUES (?, ?, ?)""",
        (inspection_id, miner_id, verdict)
    )
    conn.commit()


def get_pending_reviews(conn, limit=50):
    """Get pending review queue items."""
    rows = conn.execute(
        """SELECT rq.*, si.confidence, si.reasoning, si.inspected_at
           FROM sophia_review_queue rq
           JOIN sophia_inspections si ON rq.inspection_id = si.id
           WHERE rq.reviewed = 0
           ORDER BY si.inspected_at DESC LIMIT ?""",
        (limit,)
    ).fetchall()
    return [dict(r) for r in rows]


def mark_reviewed(conn, review_id, reviewer):
    """Mark a review queue item as reviewed."""
    conn.execute(
        """UPDATE sophia_review_queue
           SET reviewed = 1, reviewer = ?, reviewed_at = ?
           WHERE id = ?""",
        (reviewer, time.time(), review_id)
    )
    conn.commit()


def get_dashboard_stats(conn):
    """Get aggregate stats for the admin dashboard."""
    stats = {}

    row = conn.execute(
        "SELECT COUNT(*) as total FROM sophia_inspections"
    ).fetchone()
    stats["total_inspections"] = row["total"]

    rows = conn.execute(
        """SELECT verdict, COUNT(*) as cnt
           FROM sophia_inspections
           GROUP BY verdict"""
    ).fetchall()
    stats["by_verdict"] = {r["verdict"]: r["cnt"] for r in rows}

    row = conn.execute(
        """SELECT AVG(confidence) as avg_conf
           FROM sophia_inspections"""
    ).fetchone()
    stats["avg_confidence"] = round(row["avg_conf"], 4) if row["avg_conf"] else 0.0

    row = conn.execute(
        """SELECT COUNT(*) as pending
           FROM sophia_review_queue WHERE reviewed = 0"""
    ).fetchone()
    stats["pending_reviews"] = row["pending"]

    return stats


def get_low_confidence_miners(conn, threshold=0.5):
    """Find miners whose latest inspection has confidence below threshold."""
    rows = conn.execute(
        """SELECT si.*
           FROM sophia_inspections si
           INNER JOIN (
               SELECT miner_id, MAX(inspected_at) as latest
               FROM sophia_inspections GROUP BY miner_id
           ) latest ON si.miner_id = latest.miner_id
                    AND si.inspected_at = latest.latest
           WHERE si.confidence < ?""",
        (threshold,)
    ).fetchall()
    return [dict(r) for r in rows]


def get_verdict_changed_miners(conn):
    """Find miners whose last two inspections have different verdicts."""
    rows = conn.execute(
        """SELECT DISTINCT a.miner_id, a.verdict as current_verdict,
                  b.verdict as previous_verdict
           FROM sophia_inspections a
           INNER JOIN sophia_inspections b
               ON a.miner_id = b.miner_id AND a.id != b.id
           WHERE a.inspected_at = (
               SELECT MAX(inspected_at) FROM sophia_inspections
               WHERE miner_id = a.miner_id
           )
           AND b.inspected_at = (
               SELECT MAX(inspected_at) FROM sophia_inspections
               WHERE miner_id = a.miner_id AND inspected_at < a.inspected_at
           )
           AND a.verdict != b.verdict"""
    ).fetchall()
    return [dict(r) for r in rows]


def get_all_miner_ids(conn):
    """Get all distinct miner IDs."""
    rows = conn.execute(
        "SELECT DISTINCT miner_id FROM sophia_inspections"
    ).fetchall()
    return [r["miner_id"] for r in rows]
