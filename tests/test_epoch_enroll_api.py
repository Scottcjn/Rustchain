import sys

integrated_node = sys.modules["integrated_node"]


def test_epoch_enroll_requires_json_object():
    integrated_node.app.config["TESTING"] = True

    with integrated_node.app.test_client() as client:
        resp = client.post("/epoch/enroll", json=["not", "an", "object"])

    assert resp.status_code == 400
    assert resp.get_json()["error"] == "JSON object required"


def test_epoch_enroll_missing_body_uses_json_validation():
    integrated_node.app.config["TESTING"] = True

    with integrated_node.app.test_client() as client:
        resp = client.post("/epoch/enroll")

    assert resp.status_code == 400
    assert resp.get_json()["error"] == "JSON object required"
