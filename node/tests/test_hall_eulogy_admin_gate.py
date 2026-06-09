"""Regression tests for the Hall of Rust /hall/eulogy/<fingerprint> admin gate.

Issue #7244: POST /hall/eulogy/<fingerprint> previously had no _require_admin()
check, so any unauthenticated caller could deface the public memorial registry
(nickname, eulogy, is_deceased/deceased_at) for any known fingerprint.

These tests prove the fix in node/hall_of_rust.py:

- Anonymous POSTs return 401/503 and DO NOT mutate the row.
- Authenticated POSTs (correct X-Admin-Key) succeed and persist the changes.
- A nonexistent admin key is rejected even when a wrong key is supplied.
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import pytest
from flask import Flask

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "node"))

# Import the module fresh so the env var we set per-test takes effect.
import hall_of_rust  # noqa: E402


@pytest.fixture
def fresh_module(monkeypatch):
    """Reload hall_of_rust with the supplied RC_ADMIN_KEY env var."""

    def _reload(admin_key: str | None):
        if admin_key is None:
            monkeypatch.delenv("RC_ADMIN_KEY", raising=False)
        else:
            monkeypatch.setenv("RC_ADMIN_KEY", admin_key)
        # Force reimport so the module-level _require_admin reads the new value
        # on each call (it reads os.environ lazily, but Flask blueprint state
        # survives across tests within the same process, so reloading is safer).
        mod = importlib.reload(hall_of_rust)
        return mod

    return _reload


def _client_for(db_path):
    app = Flask(__name__)
    app.config["DB_PATH"] = str(db_path)
    app.register_blueprint(hall_of_rust.hall_bp)
    return app.test_client()


def _seed_hall_row(db_path, fingerprint: str = "abc123") -> None:
    """Insert one hall_of_rust row so the UPDATE has a real target."""
    hall_of_rust.init_hall_tables(str(db_path))
    import sqlite3
    import time
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            INSERT INTO hall_of_rust (
                fingerprint_hash, miner_id, first_attestation, created_at,
                nickname, eulogy, is_deceased
            ) VALUES (?, ?, ?, ?, NULL, NULL, 0)
            """,
            (fingerprint, "test-miner", int(time.time()), int(time.time())),
        )
        conn.commit()
    finally:
        conn.close()


def _row(db_path, fingerprint: str = "abc123") -> dict:
    import sqlite3
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute(
            "SELECT nickname, eulogy, is_deceased, deceased_at "
            "FROM hall_of_rust WHERE fingerprint_hash = ?",
            (fingerprint,),
        )
        return dict(cur.fetchone())
    finally:
        conn.close()


def test_set_eulogy_rejects_anonymous_request(tmp_path, fresh_module):
    """An unauthenticated POST must NOT mutate the hall_of_rust row."""
    fresh_module(admin_key="s3cret-admin-key")
    db_path = tmp_path / "hall.db"
    _seed_hall_row(db_path)
    client = _client_for(db_path)

    response = client.post(
        "/hall/eulogy/abc123",
        json={"nickname": "DEFACED", "eulogy": "unauth write"},
    )

    assert response.status_code == 401
    assert response.get_json() == {"error": "Unauthorized — admin key required"}
    # Row must be untouched.
    row = _row(db_path)
    assert row["nickname"] is None
    assert row["eulogy"] is None
    assert row["is_deceased"] == 0
    assert row["deceased_at"] is None


def test_set_eulogy_rejects_wrong_admin_key(tmp_path, fresh_module):
    fresh_module(admin_key="s3cret-admin-key")
    db_path = tmp_path / "hall.db"
    _seed_hall_row(db_path)
    client = _client_for(db_path)

    response = client.post(
        "/hall/eulogy/abc123",
        json={"nickname": "wrong-key"},
        headers={"X-Admin-Key": "guess"},
    )

    assert response.status_code == 401
    row = _row(db_path)
    assert row["nickname"] is None


def test_set_eulogy_fails_closed_when_admin_key_unset(tmp_path, fresh_module):
    """If RC_ADMIN_KEY is unset, the gate must fail with 503 (fail-closed)."""
    fresh_module(admin_key=None)
    db_path = tmp_path / "hall.db"
    _seed_hall_row(db_path)
    client = _client_for(db_path)

    response = client.post(
        "/hall/eulogy/abc123",
        json={"nickname": "no-key"},
    )

    assert response.status_code == 503
    assert response.get_json() == {"error": "RC_ADMIN_KEY not configured"}
    row = _row(db_path)
    assert row["nickname"] is None


def test_set_eulogy_accepts_correct_admin_key(tmp_path, fresh_module):
    """A POST with the correct X-Admin-Key persists the changes."""
    fresh_module(admin_key="s3cret-admin-key")
    db_path = tmp_path / "hall.db"
    _seed_hall_row(db_path)
    client = _client_for(db_path)

    response = client.post(
        "/hall/eulogy/abc123",
        json={"nickname": "Old Ironsides", "eulogy": "Faithful to the end."},
        headers={"X-Admin-Key": "s3cret-admin-key"},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body == {"ok": True, "message": "Memorial updated"}
    row = _row(db_path)
    assert row["nickname"] == "Old Ironsides"
    assert row["eulogy"] == "Faithful to the end."


def test_set_eulogy_admin_can_mark_deceased(tmp_path, fresh_module):
    """A POST with is_deceased=true and a valid key sets the deceased fields."""
    fresh_module(admin_key="s3cret-admin-key")
    db_path = tmp_path / "hall.db"
    _seed_hall_row(db_path)
    client = _client_for(db_path)

    response = client.post(
        "/hall/eulogy/abc123",
        json={"is_deceased": True},
        headers={"X-Admin-Key": "s3cret-admin-key"},
    )

    assert response.status_code == 200
    row = _row(db_path)
    assert row["is_deceased"] == 1
    # deceased_at should be a positive integer (now-ish).
    assert isinstance(row["deceased_at"], int)
    assert row["deceased_at"] > 0


def test_set_eulogy_anonymous_cannot_mark_deceased(tmp_path, fresh_module):
    """An anonymous POST with is_deceased=true must NOT mark the row deceased."""
    fresh_module(admin_key="s3cret-admin-key")
    db_path = tmp_path / "hall.db"
    _seed_hall_row(db_path)
    client = _client_for(db_path)

    response = client.post(
        "/hall/eulogy/abc123",
        json={"is_deceased": True, "nickname": "GHOST"},
    )

    assert response.status_code == 401
    row = _row(db_path)
    assert row["is_deceased"] == 0
    assert row["deceased_at"] is None
    assert row["nickname"] is None
