# SPDX-License-Identifier: MIT
"""Regression tests for authenticated OUI deny route JSON validation."""

import sys

import pytest


integrated_node = sys.modules["integrated_node"]
ADMIN_HEADERS = {"X-Admin-Key": "0" * 32}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("RC_ADMIN_KEY", "0" * 32)
    integrated_node.app.config["TESTING"] = True
    with integrated_node.app.test_client() as c:
        yield c


@pytest.mark.parametrize("path", ["/admin/oui_deny/add", "/admin/oui_deny/remove"])
def test_oui_deny_rejects_non_object_json(client, path):
    response = client.post(path, headers=ADMIN_HEADERS, json=["not", "object"])

    assert response.status_code == 400
    assert response.get_json() == {"error": "Invalid JSON body"}


def test_oui_enforce_rejects_non_object_json(client):
    response = client.post("/admin/oui_deny/enforce", headers=ADMIN_HEADERS, json=["not", "object"])

    assert response.status_code == 400
    assert response.get_json() == {"error": "Invalid JSON body"}


@pytest.mark.parametrize("path", ["/admin/oui_deny/add", "/admin/oui_deny/remove"])
def test_oui_deny_rejects_non_string_oui(client, path):
    response = client.post(path, headers=ADMIN_HEADERS, json={"oui": ["aa", "bb", "cc"]})

    assert response.status_code == 400
    assert response.get_json() == {"error": "OUI must be a string"}


def test_oui_deny_add_rejects_invalid_enforce(client):
    response = client.post(
        "/admin/oui_deny/add",
        headers=ADMIN_HEADERS,
        json={"oui": "aa:bb:cc", "enforce": "yes"},
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": "enforce must be an integer"}


def test_oui_deny_add_rejects_boolean_enforce(client):
    response = client.post(
        "/admin/oui_deny/add",
        headers=ADMIN_HEADERS,
        json={"oui": "aa:bb:cc", "enforce": True},
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": "enforce must be an integer"}


def test_oui_deny_add_rejects_non_string_vendor(client):
    response = client.post(
        "/admin/oui_deny/add",
        headers=ADMIN_HEADERS,
        json={"oui": "aa:bb:cc", "vendor": {"name": "vmware"}},
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": "Vendor must be a string"}
