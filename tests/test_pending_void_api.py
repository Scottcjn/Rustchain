import sys

integrated_node = sys.modules["integrated_node"]


def _admin_headers():
    return {"X-Admin-Key": "test-admin-key"}


def test_pending_void_requires_json_object(monkeypatch):
    monkeypatch.setenv("RC_ADMIN_KEY", "test-admin-key")
    integrated_node.app.config["TESTING"] = True

    with integrated_node.app.test_client() as client:
        resp = client.post(
            "/pending/void",
            headers=_admin_headers(),
            json=["not", "an", "object"],
        )

    assert resp.status_code == 400
    assert resp.get_json()["error"] == "JSON object required"


def test_pending_void_rejects_non_scalar_pending_id(monkeypatch):
    monkeypatch.setenv("RC_ADMIN_KEY", "test-admin-key")
    integrated_node.app.config["TESTING"] = True

    with integrated_node.app.test_client() as client:
        resp = client.post(
            "/pending/void",
            headers=_admin_headers(),
            json={"pending_id": ["not", "scalar"]},
        )

    assert resp.status_code == 400
    assert resp.get_json()["error"] == "pending_id must be a string or integer"


def test_pending_void_rejects_non_string_tx_hash(monkeypatch):
    monkeypatch.setenv("RC_ADMIN_KEY", "test-admin-key")
    integrated_node.app.config["TESTING"] = True

    with integrated_node.app.test_client() as client:
        resp = client.post(
            "/pending/void",
            headers=_admin_headers(),
            json={"tx_hash": {"not": "scalar"}},
        )

    assert resp.status_code == 400
    assert resp.get_json()["error"] == "tx_hash must be a string"
