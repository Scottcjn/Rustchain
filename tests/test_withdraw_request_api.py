import sys

integrated_node = sys.modules["integrated_node"]


def test_withdraw_request_requires_json_object():
    integrated_node.app.config["TESTING"] = True

    with integrated_node.app.test_client() as client:
        resp = client.post("/withdraw/request", json=["not", "an", "object"])

    assert resp.status_code == 400
    assert resp.get_json()["error"] == "JSON object required"


def test_withdraw_request_rejects_invalid_amount_before_database():
    integrated_node.app.config["TESTING"] = True

    with integrated_node.app.test_client() as client:
        resp = client.post(
            "/withdraw/request",
            json={
                "miner_pk": "miner-a",
                "amount": "not-a-number",
                "destination": "dest",
                "signature": "sig",
                "nonce": "nonce-1",
            },
        )

    assert resp.status_code == 400
    assert resp.get_json()["error"] == "Invalid amount"


def test_withdraw_request_rejects_nan_amount_before_database():
    integrated_node.app.config["TESTING"] = True

    with integrated_node.app.test_client() as client:
        resp = client.post(
            "/withdraw/request",
            json={
                "miner_pk": "miner-a",
                "amount": "nan",
                "destination": "dest",
                "signature": "sig",
                "nonce": "nonce-2",
            },
        )

    assert resp.status_code == 400
    assert resp.get_json()["error"] == "Invalid amount"


def test_withdraw_request_rejects_infinite_amount_before_database():
    integrated_node.app.config["TESTING"] = True

    with integrated_node.app.test_client() as client:
        resp = client.post(
            "/withdraw/request",
            json={
                "miner_pk": "miner-a",
                "amount": "inf",
                "destination": "dest",
                "signature": "sig",
                "nonce": "nonce-3",
            },
        )

    assert resp.status_code == 400
    assert resp.get_json()["error"] == "Invalid amount"
