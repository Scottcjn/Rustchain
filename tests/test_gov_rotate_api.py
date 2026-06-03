import sys

integrated_node = sys.modules["integrated_node"]


def _admin_headers():
    return {"X-API-Key": "test-admin-key"}


def _member(signer_id=1):
    return {"signer_id": signer_id, "pubkey_hex": "aa"}


def test_gov_rotate_stage_requires_json_object(monkeypatch):
    monkeypatch.setattr(integrated_node, "ADMIN_KEY", "test-admin-key")
    integrated_node.app.config["TESTING"] = True

    with integrated_node.app.test_client() as client:
        resp = client.post(
            "/gov/rotate/stage",
            headers=_admin_headers(),
            json=["not", "an", "object"],
        )

    assert resp.status_code == 400
    assert resp.get_json()["reason"] == "json_object_required"


def test_gov_rotate_stage_rejects_bad_integer_fields(monkeypatch):
    monkeypatch.setattr(integrated_node, "ADMIN_KEY", "test-admin-key")
    integrated_node.app.config["TESTING"] = True

    with integrated_node.app.test_client() as client:
        resp = client.post(
            "/gov/rotate/stage",
            headers=_admin_headers(),
            json={
                "epoch_effective": "bad",
                "threshold": 3,
                "members": [_member()],
            },
        )

    assert resp.status_code == 400
    assert resp.get_json()["reason"] == "bad_args"


def test_gov_rotate_stage_rejects_non_positive_threshold(monkeypatch):
    monkeypatch.setattr(integrated_node, "ADMIN_KEY", "test-admin-key")
    integrated_node.app.config["TESTING"] = True

    with integrated_node.app.test_client() as client:
        resp = client.post(
            "/gov/rotate/stage",
            headers=_admin_headers(),
            json={
                "epoch_effective": 1,
                "threshold": 0,
                "members": [_member()],
            },
        )

    assert resp.status_code == 400
    assert resp.get_json()["reason"] == "invalid_threshold"


def test_gov_rotate_stage_rejects_threshold_above_members(monkeypatch):
    monkeypatch.setattr(integrated_node, "ADMIN_KEY", "test-admin-key")
    integrated_node.app.config["TESTING"] = True

    with integrated_node.app.test_client() as client:
        resp = client.post(
            "/gov/rotate/stage",
            headers=_admin_headers(),
            json={
                "epoch_effective": 1,
                "threshold": 2,
                "members": [_member()],
            },
        )

    assert resp.status_code == 400
    assert resp.get_json()["reason"] == "threshold_exceeds_members"


def test_gov_rotate_approve_rejects_bad_integer_fields():
    integrated_node.app.config["TESTING"] = True

    with integrated_node.app.test_client() as client:
        resp = client.post(
            "/gov/rotate/approve",
            json={"epoch_effective": "bad", "signer_id": 1, "sig_hex": "aa"},
        )

    assert resp.status_code == 400
    assert resp.get_json()["reason"] == "bad_args"


def test_gov_rotate_commit_requires_json_object():
    integrated_node.app.config["TESTING"] = True

    with integrated_node.app.test_client() as client:
        resp = client.post("/gov/rotate/commit", json=["not", "an", "object"])

    assert resp.status_code == 400
    assert resp.get_json()["reason"] == "json_object_required"
