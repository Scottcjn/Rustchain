# SPDX-License-Identifier: MIT

import os
import sys

from flask import Flask
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import rustchain_sync_endpoints


class DummySyncManager:
    SYNC_TABLES = ["headers", "balances"]

    def __init__(self, db_path, admin_key):
        self.db_path = db_path
        self.admin_key = admin_key
        self.calls = []

    def get_sync_status(self):
        return {"merkle_root": "test-root"}

    def get_table_data(self, table, limit=200, offset=0):
        self.calls.append((table, limit, offset))
        return [{"table": table, "limit": limit, "offset": offset}]


def test_require_admin_uses_constant_time_compare(monkeypatch, tmp_path):
    """Sync admin endpoints check API keys through hmac.compare_digest."""
    monkeypatch.setattr(rustchain_sync_endpoints, "RustChainSyncManager", DummySyncManager)
    calls = []

    def spy_compare_digest(provided, expected):
        calls.append((provided, expected))
        return provided == expected

    monkeypatch.setattr(rustchain_sync_endpoints.hmac, "compare_digest", spy_compare_digest)

    app = Flask(__name__)
    rustchain_sync_endpoints.register_sync_endpoints(
        app,
        str(tmp_path / "rustchain.db"),
        "sync-secret",
    )
    client = app.test_client()

    denied = client.get("/api/sync/status", headers={"X-Admin-Key": "wrong-secret"})
    assert denied.status_code == 401

    accepted = client.get("/api/sync/status", headers={"X-API-Key": "sync-secret"})
    assert accepted.status_code == 200
    assert accepted.get_json()["merkle_root"] == "test-root"

    assert calls == [
        ("wrong-secret", "sync-secret"),
        ("sync-secret", "sync-secret"),
    ]


@pytest.mark.parametrize("admin_key", [None, ""])
def test_sync_admin_auth_fails_closed_when_admin_key_unconfigured(
    monkeypatch, tmp_path, admin_key
):
    """Missing sync admin key must reject requests instead of crashing."""
    monkeypatch.setattr(rustchain_sync_endpoints, "RustChainSyncManager", DummySyncManager)
    calls = []

    def spy_compare_digest(provided, expected):
        calls.append((provided, expected))
        return provided == expected

    monkeypatch.setattr(rustchain_sync_endpoints.hmac, "compare_digest", spy_compare_digest)

    app = Flask(__name__)
    rustchain_sync_endpoints.register_sync_endpoints(
        app,
        str(tmp_path / "rustchain.db"),
        admin_key,
    )
    client = app.test_client()

    response = client.get("/api/sync/status", headers={"X-Admin-Key": "anything"})

    assert response.status_code == 401
    assert response.get_json() == {"error": "Unauthorized"}
    assert calls == []


def test_sync_pull_validates_and_clamps_query_bounds(monkeypatch, tmp_path):
    monkeypatch.setattr(rustchain_sync_endpoints, "RustChainSyncManager", DummySyncManager)

    app = Flask(__name__)
    rustchain_sync_endpoints.register_sync_endpoints(
        app,
        str(tmp_path / "rustchain.db"),
        "sync-secret",
    )
    client = app.test_client()

    response = client.get(
        "/api/sync/pull?table=headers&limit=5000&offset=-10",
        headers={"X-Admin-Key": "sync-secret"},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["meta"] == {
        "limit": 1000,
        "offset": 0,
        "tables": ["headers"],
    }
    assert body["data"]["headers"] == [{"table": "headers", "limit": 1000, "offset": 0}]


def test_sync_pull_uses_defaults_for_empty_query_values(monkeypatch, tmp_path):
    monkeypatch.setattr(rustchain_sync_endpoints, "RustChainSyncManager", DummySyncManager)

    app = Flask(__name__)
    rustchain_sync_endpoints.register_sync_endpoints(
        app,
        str(tmp_path / "rustchain.db"),
        "sync-secret",
    )
    client = app.test_client()

    response = client.get(
        "/api/sync/pull?limit=&offset=",
        headers={"X-Admin-Key": "sync-secret"},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["meta"] == {
        "limit": 200,
        "offset": 0,
        "tables": ["headers", "balances"],
    }


@pytest.mark.parametrize(
    ("query", "error"),
    [
        ("limit=abc", "limit must be an integer"),
        ("offset=soon", "offset must be an integer"),
    ],
)
def test_sync_pull_rejects_malformed_query_values(monkeypatch, tmp_path, query, error):
    monkeypatch.setattr(rustchain_sync_endpoints, "RustChainSyncManager", DummySyncManager)

    app = Flask(__name__)
    rustchain_sync_endpoints.register_sync_endpoints(
        app,
        str(tmp_path / "rustchain.db"),
        "sync-secret",
    )
    client = app.test_client()

    response = client.get(
        f"/api/sync/pull?{query}",
        headers={"X-Admin-Key": "sync-secret"},
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": error}


def test_sync_pull_rejects_unknown_table(monkeypatch, tmp_path):
    monkeypatch.setattr(rustchain_sync_endpoints, "RustChainSyncManager", DummySyncManager)

    app = Flask(__name__)
    rustchain_sync_endpoints.register_sync_endpoints(
        app,
        str(tmp_path / "rustchain.db"),
        "sync-secret",
    )
    client = app.test_client()

    response = client.get(
        "/api/sync/pull?table=unknown",
        headers={"X-Admin-Key": "sync-secret"},
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": "invalid table: unknown"}
