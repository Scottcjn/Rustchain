import pytest
from flask import Flask

from node.rustchain_bft_consensus import BFTConsensus, create_bft_routes


@pytest.fixture
def bft_client():
    app = Flask(__name__)
    app.config["TESTING"] = True
    bft = BFTConsensus("node-a", ":memory:", "test-secret")
    create_bft_routes(app, bft)

    try:
        yield app.test_client()
    finally:
        bft._cancel_view_change_timer()


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
        "error": "missing required fields: epoch, signature, timestamp"
    }
