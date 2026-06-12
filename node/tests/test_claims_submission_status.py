import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from claims_submission import update_claim_status


def _init_claim_status_db(db_path):
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE claims (
                claim_id TEXT PRIMARY KEY,
                status TEXT,
                updated_at INTEGER,
                verified_at INTEGER,
                transaction_hash TEXT,
                settlement_batch TEXT,
                settled_at INTEGER,
                rejection_reason TEXT
            );
            CREATE TABLE claims_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                claim_id TEXT NOT NULL,
                action TEXT NOT NULL,
                actor TEXT,
                details TEXT,
                timestamp INTEGER NOT NULL
            );
            """
        )


def test_update_claim_status_missing_claim_returns_false_without_audit(tmp_path):
    db_path = str(tmp_path / "claims.db")
    _init_claim_status_db(db_path)

    ok = update_claim_status(
        db_path,
        "missing-claim",
        "settled",
        {"transaction_hash": "0xabc", "settlement_batch": "batch-1"},
    )

    assert ok is False
    with sqlite3.connect(db_path) as conn:
        audit_count = conn.execute("SELECT COUNT(*) FROM claims_audit").fetchone()[0]
    assert audit_count == 0
