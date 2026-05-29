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

def test_ingest_signed_header_rejects_miner_mismatch(client):
    response = client.post(
        "/headers/ingest_signed",
        json={
            "miner_id": "miner-a",
            "header": {"miner": "miner-b", "slot": 1},
            "message": "00",
            "signature": "0" * 128,
        },
    )

    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "miner_header_mismatch"}


def test_ingest_signed_header_rejects_non_slot_producer(client, monkeypatch):
    monkeypatch.setattr(integrated_node, "TESTNET_ALLOW_INLINE_PUBKEY", True)
    monkeypatch.setattr(integrated_node, "TESTNET_ALLOW_MOCK_SIG", True)
    monkeypatch.setattr(integrated_node, "current_slot", lambda: 100)
    monkeypatch.setattr(
        integrated_node,
        "check_eligibility_round_robin",
        lambda _db_path, miner_id, slot, _now: {
            "eligible": False,
            "reason": "wrong_slot_producer",
            "slot_producer": "miner-b",
            "rotation_size": 2,
        },
        raising=False,
    )

    response = client.post(
        "/headers/ingest_signed",
        json={
            "miner_id": "miner-a",
            "header": {"miner": "miner-a", "slot": 100},
            "message": "00",
            "signature": "0" * 128,
            "pubkey": "1" * 64,
        },
    )

    assert response.status_code == 403
    assert response.get_json() == {
        "ok": False,
        "error": "not_slot_producer",
        "reason": "wrong_slot_producer",
        "slot_producer": "miner-b",
        "rotation_size": 2,
    }

