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


def _insert_claim(db_path, claim_id, status="verifying"):
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO claims (claim_id, status, updated_at) VALUES (?, ?, 0)",
            (claim_id, status),
        )


def _verified_at(db_path, claim_id):
    with sqlite3.connect(db_path) as conn:
        return conn.execute(
            "SELECT verified_at FROM claims WHERE claim_id = ?", (claim_id,)
        ).fetchone()[0]


def test_approved_stamps_verified_at(tmp_path):
    db_path = str(tmp_path / "claims.db")
    _init_claim_status_db(db_path)
    _insert_claim(db_path, "c1")

    assert update_claim_status(db_path, "c1", "approved") is True
    assert _verified_at(db_path, "c1") is not None


def test_settled_preserves_verified_at(tmp_path):
    # Real lifecycle: approved -> settled. The verification timestamp set at
    # approval must survive settlement instead of being clobbered to NULL.
    db_path = str(tmp_path / "claims.db")
    _init_claim_status_db(db_path)
    _insert_claim(db_path, "c1")

    update_claim_status(db_path, "c1", "approved")
    verified_at = _verified_at(db_path, "c1")
    assert verified_at is not None

    update_claim_status(
        db_path,
        "c1",
        "settled",
        {"transaction_hash": "0xabc", "settlement_batch": "batch-1"},
    )
    assert _verified_at(db_path, "c1") == verified_at


def test_non_verification_status_does_not_set_verified_at(tmp_path):
    # A claim that never reached approval must not gain a verified_at just
    # because it moved to another status (e.g. verifying).
    db_path = str(tmp_path / "claims.db")
    _init_claim_status_db(db_path)
    _insert_claim(db_path, "c1", status="pending")

    update_claim_status(db_path, "c1", "verifying")
    assert _verified_at(db_path, "c1") is None
