import os

from flask import Flask

os.environ.setdefault("RC_P2P_SECRET", "a" * 64)

from node.rustchain_p2p_gossip import register_p2p_endpoints


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
