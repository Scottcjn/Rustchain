import os

from flask import Flask

os.environ.setdefault("RC_P2P_SECRET", "a" * 64)

import pytest

from node.rustchain_p2p_gossip import (
    GOSSIP_TTL,
    GossipMessage,
    MAX_GOSSIP_PAYLOAD_OBJECT_KEYS,
    MAX_GOSSIP_PAYLOAD_SERIALIZED_BYTES,
    MessageType,
    register_p2p_endpoints,
)


class _FakeP2PNode:
    def __init__(self):
        self.handled = []
        self.node_id = "node-test"
        self.running = True
        self.peers = {}
        self.gossip = type(
            "FakeGossip",
            (),
            {
                "attestation_crdt": type("FakeAttest", (), {"data": {}})(),
                "epoch_crdt": type("FakeEpoch", (), {"items": set()})(),
            },
        )()

    def handle_gossip(self, data):
        self.handled.append(data)
        return {"status": "ok"}

    def get_full_state(self):
        return {"node_id": self.node_id}

    def get_attestation_state(self):
        return {"node_id": self.node_id, "attestations": {}}


def _app_and_node():
    app = Flask(__name__)
    app.config["TESTING"] = True
    node = _FakeP2PNode()
    register_p2p_endpoints(app, node)
    return app, node


def test_p2p_gossip_requires_json_object():
    app, node = _app_and_node()

    with app.test_client() as client:
        resp = client.post("/p2p/gossip", json=["not", "an", "object"])

    assert resp.status_code == 400
    assert resp.get_json()["error"] == "JSON object required"
    assert node.handled == []


def test_p2p_gossip_forwards_valid_object_body():
    app, node = _app_and_node()
    payload = {"msg_type": "ping"}

    with app.test_client() as client:
        resp = client.post("/p2p/gossip", json=payload)

    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"
    assert node.handled == [payload]


def test_p2p_gossip_rejects_oversized_payload_before_handler():
    app, node = _app_and_node()
    payload = {
        "msg_type": MessageType.PING.value,
        "msg_id": "msg-oversized",
        "sender_id": "peer-1",
        "timestamp": 1,
        "ttl": GOSSIP_TTL,
        "signature": "bad-signature",
        "payload": {
            f"k{i:04d}": "x"
            for i in range(MAX_GOSSIP_PAYLOAD_OBJECT_KEYS + 1)
        },
    }

    with app.test_client() as client:
        resp = client.post("/p2p/gossip", json=payload)

    assert resp.status_code == 400
    assert "too many keys" in resp.get_json()["error"]
    assert node.handled == []


def test_gossip_message_rejects_payload_that_exceeds_serialized_cap():
    payload = {
        "msg_type": MessageType.PING.value,
        "msg_id": "msg-large-string",
        "sender_id": "peer-1",
        "timestamp": 1,
        "ttl": GOSSIP_TTL,
        "signature": "bad-signature",
        "payload": {
            "chunks": ["x" * 128]
            * (MAX_GOSSIP_PAYLOAD_SERIALIZED_BYTES // 128),
        },
    }

    with pytest.raises(ValueError, match="maximum serialized size"):
        GossipMessage.from_dict(payload)
