# SPDX-License-Identifier: MIT

import sys

import pytest

integrated_node = sys.modules["integrated_node"]


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("RC_ADMIN_KEY", "0" * 32)
    integrated_node.app.config["TESTING"] = True
    with integrated_node.app.test_client() as test_client:
        yield test_client


def test_miner_headerkey_rejects_non_object_json(client):
    response = client.post(
        "/miner/headerkey",
        headers={"X-API-Key": "0" * 32},
        json=["not", "an", "object"],
    )

    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "invalid_json_body"}


def test_ingest_signed_header_rejects_non_object_json(client):
    response = client.post("/headers/ingest_signed", json=["not", "an", "object"])

    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "invalid_json_body"}
