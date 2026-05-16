from flask import Flask

from node.rustchain_bft_consensus import create_bft_routes


class _FakeBft:
    def get_status(self):
        return {"ok": True}

    def receive_message(self, msg_data):
        return None

    def handle_view_change(self, msg_data):
        return None

    def propose_epoch_settlement(self, epoch, miners, distribution):
        return None


def _client():
    app = Flask(__name__)
    app.config["TESTING"] = True
    create_bft_routes(app, _FakeBft())
    return app.test_client()


def test_bft_propose_requires_json_object():
    resp = _client().post("/bft/propose", json=["not", "an", "object"])

    assert resp.status_code == 400
    assert resp.get_json()["error"] == "JSON object required"


def test_bft_propose_requires_epoch_field():
    resp = _client().post(
        "/bft/propose",
        json={"miners": [], "distribution": {}},
    )

    assert resp.status_code == 400
    assert resp.get_json()["error"] == "Missing epoch field"


def test_bft_propose_rejects_invalid_collection_fields():
    client = _client()

    miners_resp = client.post(
        "/bft/propose",
        json={"epoch": 1, "miners": {"bad": "shape"}, "distribution": {}},
    )
    distribution_resp = client.post(
        "/bft/propose",
        json={"epoch": 1, "miners": [], "distribution": ["bad", "shape"]},
    )

    assert miners_resp.status_code == 400
    assert miners_resp.get_json()["error"] == "miners must be a list"
    assert distribution_resp.status_code == 400
    assert distribution_resp.get_json()["error"] == "distribution must be an object"
