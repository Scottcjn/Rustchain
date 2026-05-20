import hashlib
import hmac
import time

import pytest
from flask import Flask

from node.rustchain_bft_consensus import BFTConsensus, create_bft_routes


@pytest.fixture
def bft_context():
    app = Flask(__name__)
    app.config["TESTING"] = True
    bft = BFTConsensus("node-a", ":memory:", "test-secret")
    create_bft_routes(app, bft)

    try:
        with app.test_client() as client:
            yield client, bft
    finally:
        bft._cancel_view_change_timer()


@pytest.fixture
def bft_client(bft_context):
    client, _ = bft_context
    return client


def _signed_view_change(bft, *, view=1, epoch=0):
    timestamp = int(time.time())
    sign_data = f"view_change:{view}:{epoch}:{timestamp}"
    node_key = bft._derive_node_key("peer-a")
    signature = hmac.new(
        node_key.encode(),
        sign_data.encode(),
        hashlib.sha256,
    ).hexdigest()
    return {
        "view": view,
        "epoch": epoch,
        "node_id": "peer-a",
        "prepared_cert": None,
        "signature": signature,
        "timestamp": timestamp,
    }


def _raise_runtime_error(message):
    raise RuntimeError(message)


@pytest.mark.parametrize("payload", (None, [], "not-object"))
def test_bft_message_requires_json_object(bft_client, payload):
    response = bft_client.post("/bft/message", json=payload)

    assert response.status_code == 400
    assert response.get_json() == {"error": "JSON object required"}


@pytest.mark.parametrize("payload", ({}, {"msg_type": "unknown"}))
def test_bft_message_rejects_invalid_message_type(bft_client, payload):
    response = bft_client.post("/bft/message", json=payload)

    assert response.status_code == 400
    assert response.get_json() == {"error": "invalid msg_type"}


def test_bft_message_hides_internal_exception_details(bft_context, monkeypatch):
    client, bft = bft_context
    secret_detail = "sqlite error: no such table: bft_message_log"
    monkeypatch.setattr(
        bft,
        "receive_message",
        lambda _data: _raise_runtime_error(secret_detail),
    )

    response = client.post("/bft/message", json={"msg_type": "prepare"})

    assert response.status_code == 400
    body = response.get_json()
    assert body == {"error": "BFT message processing failed"}
    assert secret_detail not in str(body)


@pytest.mark.parametrize("payload", (None, [], "not-object"))
def test_bft_view_change_requires_json_object(bft_client, payload):
    response = bft_client.post("/bft/view_change", json=payload)

    assert response.status_code == 400
    assert response.get_json() == {"error": "JSON object required"}


def test_bft_view_change_rejects_missing_required_fields(bft_client):
    response = bft_client.post(
        "/bft/view_change",
        json={"view": 2, "node_id": "peer-a"},
    )

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "missing required fields: epoch, prepared_cert, signature, timestamp"
    }


def test_bft_view_change_rejects_invalid_signature(bft_context):
    client, bft = bft_context

    response = client.post(
        "/bft/view_change",
        json={
            "view": 1,
            "epoch": 0,
            "node_id": "peer-a",
            "prepared_cert": None,
            "signature": "not-a-valid-signature",
            "timestamp": int(time.time()),
        },
    )

    assert response.status_code == 401
    assert response.get_json() == {"error": "invalid signature"}
    assert bft.view_change_log == {}


def test_bft_view_change_accepts_valid_signature(bft_context):
    client, bft = bft_context
    payload = _signed_view_change(bft)

    response = client.post("/bft/view_change", json=payload)

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}
    assert bft.view_change_log[payload["view"]]["peer-a"].node_id == "peer-a"


def test_bft_view_change_hides_internal_exception_details(bft_context, monkeypatch):
    client, bft = bft_context
    secret_detail = "config path leaked: /var/lib/rustchain/bft.db"
    monkeypatch.setattr(
        bft,
        "handle_view_change",
        lambda _data: _raise_runtime_error(secret_detail),
    )

    response = client.post("/bft/view_change", json=_signed_view_change(bft))

    assert response.status_code == 400
    body = response.get_json()
    assert body == {"error": "BFT view change processing failed"}
    assert secret_detail not in str(body)


def test_bft_propose_hides_internal_exception_details(bft_context, monkeypatch):
    client, bft = bft_context
    secret_detail = "sqlite error: no such table: bft_committed_epochs"
    monkeypatch.setattr(
        bft,
        "propose_epoch_settlement",
        lambda _epoch, _miners, _distribution: _raise_runtime_error(secret_detail),
    )

    response = client.post(
        "/bft/propose",
        json={"epoch": 1, "miners": [], "distribution": {}},
    )

    assert response.status_code == 500
    body = response.get_json()
    assert body == {"error": "BFT proposal failed"}
    assert secret_detail not in str(body)
