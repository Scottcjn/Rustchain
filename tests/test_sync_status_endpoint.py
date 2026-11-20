# SPDX-License-Identifier: MIT
"""
Tests for node sync status and monitoring health endpoints (#8507, #8617).

/health/sync and /api/sync-status must return canonical JSON, and must fail
loudly (503, ok:false) when the chain DB cannot be read -- a health check that
reports healthy while its storage is broken hides a dead node.
"""

import os
import sqlite3
import sys
from pathlib import Path

import pytest

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "node"))

NET_SLOT = 1_000_000


@pytest.fixture
def node(monkeypatch):
    mod = sys.modules.get("integrated_node")
    if not mod:
        import tests.conftest as conftest
        mod = conftest.load_node_module("integrated_node", "rustchain_v2_integrated_v2.2.1_rip200.py")
    # Pin the network slot so assertions do not race the wall clock.
    monkeypatch.setattr(mod, "current_slot", lambda: NET_SLOT)
    return mod


def _make_db(path, with_headers=True, tip=None):
    with sqlite3.connect(path) as db:
        if with_headers:
            db.execute("CREATE TABLE headers (slot INTEGER PRIMARY KEY, header_json TEXT)")
            if tip is not None:
                db.execute("INSERT INTO headers (slot, header_json) VALUES (?, '{}')", (tip,))
        else:
            db.execute("CREATE TABLE unrelated (x INTEGER)")


@pytest.mark.parametrize("route", ["/health/sync", "/api/sync-status"])
def test_synced_node_reports_ok(node, monkeypatch, tmp_path, route):
    db_path = str(tmp_path / "node.db")
    _make_db(db_path, tip=NET_SLOT - 1)
    monkeypatch.setattr(node, "DB_PATH", db_path)

    resp = node.app.test_client().get(route)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data == {
        "ok": True,
        "is_synced": True,
        "current_block": NET_SLOT - 1,
        "network_block": NET_SLOT,
        "lag_slots": 1,
    }


def test_lagging_node_is_ok_but_not_synced(node, monkeypatch, tmp_path):
    db_path = str(tmp_path / "node.db")
    _make_db(db_path, tip=NET_SLOT - 50)
    monkeypatch.setattr(node, "DB_PATH", db_path)

    resp = node.app.test_client().get("/health/sync")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert data["is_synced"] is False
    assert data["lag_slots"] == 50


def test_empty_headers_table_is_ok_not_synced(node, monkeypatch, tmp_path):
    db_path = str(tmp_path / "node.db")
    _make_db(db_path)
    monkeypatch.setattr(node, "DB_PATH", db_path)

    resp = node.app.test_client().get("/health/sync")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert data["current_block"] == 0
    assert data["is_synced"] is False


def test_missing_db_file_returns_503_and_creates_nothing(node, monkeypatch, tmp_path):
    db_path = str(tmp_path / "does-not-exist.db")
    monkeypatch.setattr(node, "DB_PATH", db_path)

    resp = node.app.test_client().get("/health/sync")
    assert resp.status_code == 503
    data = resp.get_json()
    assert data["ok"] is False
    assert data["is_synced"] is False
    assert data["error"] == "db_unavailable"
    # The probe must not silently create an empty DB at the wrong path.
    assert not os.path.exists(db_path)


def test_missing_parent_dir_returns_503(node, monkeypatch, tmp_path):
    monkeypatch.setattr(node, "DB_PATH", str(tmp_path / "no-such-dir" / "node.db"))

    resp = node.app.test_client().get("/api/sync-status")
    assert resp.status_code == 503
    assert resp.get_json()["error"] == "db_unavailable"


def test_corrupt_db_returns_503(node, monkeypatch, tmp_path):
    db_path = tmp_path / "corrupt.db"
    db_path.write_bytes(b"this is not a sqlite database" * 100)
    monkeypatch.setattr(node, "DB_PATH", str(db_path))

    resp = node.app.test_client().get("/health/sync")
    assert resp.status_code == 503
    data = resp.get_json()
    assert data["ok"] is False
    assert data["error"] == "db_unavailable"


def test_missing_headers_table_returns_503(node, monkeypatch, tmp_path):
    db_path = str(tmp_path / "node.db")
    _make_db(db_path, with_headers=False)
    monkeypatch.setattr(node, "DB_PATH", db_path)

    resp = node.app.test_client().get("/health/sync")
    assert resp.status_code == 503
    data = resp.get_json()
    assert data["ok"] is False
    assert data["error"] == "headers_table_missing"


def test_locked_db_returns_503(node, monkeypatch, tmp_path):
    db_path = str(tmp_path / "node.db")
    _make_db(db_path, tip=NET_SLOT)
    monkeypatch.setattr(node, "DB_PATH", db_path)

    real_open = node._open_db_readonly
    monkeypatch.setattr(node, "_open_db_readonly", lambda p: real_open(p, timeout=0.05))

    holder = sqlite3.connect(db_path)
    try:
        holder.execute("PRAGMA locking_mode=EXCLUSIVE")
        holder.execute("BEGIN EXCLUSIVE")
        resp = node.app.test_client().get("/health/sync")
    finally:
        holder.rollback()
        holder.close()
    assert resp.status_code == 503
    assert resp.get_json()["error"] == "db_unavailable"


def test_current_slot_failure_returns_json_503(node, monkeypatch, tmp_path):
    db_path = str(tmp_path / "node.db")
    _make_db(db_path, tip=NET_SLOT)
    monkeypatch.setattr(node, "DB_PATH", db_path)

    def boom():
        raise RuntimeError("clock unavailable")

    monkeypatch.setattr(node, "current_slot", boom)
    resp = node.app.test_client().get("/health/sync")
    assert resp.status_code == 503
    assert resp.is_json
    data = resp.get_json()
    assert data["ok"] is False
    assert data["error"] == "sync_status_unavailable"
    # Internal exception text is not leaked to unauthenticated callers.
    assert "clock unavailable" not in resp.get_data(as_text=True)
