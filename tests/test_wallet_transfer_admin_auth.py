# SPDX-License-Identifier: MIT

import sys
from types import SimpleNamespace

integrated_node = sys.modules["integrated_node"]


def _make_client(monkeypatch):
    integrated_node.app.config["TESTING"] = True
    monkeypatch.setattr(
        integrated_node,
        "validate_wallet_transfer_admin",
        lambda data: SimpleNamespace(ok=False, error="sentinel", details={}),
    )
    return integrated_node.app.test_client()


def test_wallet_transfer_fails_closed_when_admin_key_unconfigured(monkeypatch):
    monkeypatch.delenv("RC_ADMIN_KEY", raising=False)
    client = _make_client(monkeypatch)

    response = client.post("/wallet/transfer", json={}, headers={"X-Admin-Key": ""})

    assert response.status_code == 503
    body = response.get_json()
    assert body["error"] == "RC_ADMIN_KEY not configured on server"
    assert body["code"] == "ADMIN_KEY_UNSET"


def test_wallet_transfer_rejects_wrong_admin_key(monkeypatch):
    monkeypatch.setenv("RC_ADMIN_KEY", "expected-admin-key-0000000000000000")
    client = _make_client(monkeypatch)

    response = client.post("/wallet/transfer", json={}, headers={"X-Admin-Key": "wrong-key"})

    assert response.status_code == 401
    body = response.get_json()
    assert body["error"] == "Unauthorized - admin key required"


def test_wallet_transfer_accepts_valid_admin_key_or_alias(monkeypatch):
    monkeypatch.setenv("RC_ADMIN_KEY", "expected-admin-key-0000000000000000")
    client = _make_client(monkeypatch)

    response = client.post("/wallet/transfer", json={}, headers={"X-API-Key": "expected-admin-key-0000000000000000"})

    assert response.status_code == 400
    body = response.get_json()
    assert body["error"] == "sentinel"
