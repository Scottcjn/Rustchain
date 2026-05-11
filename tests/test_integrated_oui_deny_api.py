# SPDX-License-Identifier: MIT

import sys

integrated_node = sys.modules["integrated_node"]


def _admin_headers():
    return {"X-Admin-Key": "test-admin-key"}


def test_oui_deny_add_requires_json_object(monkeypatch):
    monkeypatch.setenv("RC_ADMIN_KEY", "test-admin-key")
    integrated_node.app.config["TESTING"] = True

    with integrated_node.app.test_client() as client:
        resp = client.post(
            "/admin/oui_deny/add",
            headers=_admin_headers(),
            json=["not", "an", "object"],
        )

    assert resp.status_code == 400
    assert resp.get_json()["error"] == "JSON object required"


def test_oui_deny_add_rejects_non_string_oui(monkeypatch):
    monkeypatch.setenv("RC_ADMIN_KEY", "test-admin-key")
    integrated_node.app.config["TESTING"] = True

    with integrated_node.app.test_client() as client:
        resp = client.post(
            "/admin/oui_deny/add",
            headers=_admin_headers(),
            json={"oui": {"nested": "value"}},
        )

    assert resp.status_code == 400
    assert resp.get_json()["error"] == "Invalid OUI (must be 6 hex chars)"


def test_oui_deny_add_rejects_invalid_enforce(monkeypatch):
    monkeypatch.setenv("RC_ADMIN_KEY", "test-admin-key")
    integrated_node.app.config["TESTING"] = True

    with integrated_node.app.test_client() as client:
        resp = client.post(
            "/admin/oui_deny/add",
            headers=_admin_headers(),
            json={"oui": "aa:bb:cc", "enforce": "yes"},
        )

    assert resp.status_code == 400
    assert resp.get_json()["error"] == "Invalid enforce value"


def test_oui_deny_remove_requires_json_object(monkeypatch):
    monkeypatch.setenv("RC_ADMIN_KEY", "test-admin-key")
    integrated_node.app.config["TESTING"] = True

    with integrated_node.app.test_client() as client:
        resp = client.post(
            "/admin/oui_deny/remove",
            headers=_admin_headers(),
            json=["not", "an", "object"],
        )

    assert resp.status_code == 400
    assert resp.get_json()["error"] == "JSON object required"


def test_oui_deny_remove_rejects_non_string_oui(monkeypatch):
    monkeypatch.setenv("RC_ADMIN_KEY", "test-admin-key")
    integrated_node.app.config["TESTING"] = True

    with integrated_node.app.test_client() as client:
        resp = client.post(
            "/admin/oui_deny/remove",
            headers=_admin_headers(),
            json={"oui": ["aa", "bb", "cc"]},
        )

    assert resp.status_code == 400
    assert resp.get_json()["error"] == "Invalid OUI (must be 6 hex chars)"
