# SPDX-License-Identifier: MIT

from flask import Flask

from agent_relationships import RelationshipEngine, create_relationship_blueprint


MUTATING_ENDPOINTS = (
    ("/api/relationships/alice/bob/disagree", {"topic": "model routing"}),
    ("/api/relationships/alice/bob/collaborate", {"description": "shared runbook"}),
    ("/api/relationships/alice/bob/reconcile", {"description": "postmortem"}),
)

ALL_MUTATING_ENDPOINTS = MUTATING_ENDPOINTS + (
    ("/api/relationships/alice/bob/intervene", {"reason": "moderation reset"}),
)


def _build_client(tmp_path):
    engine = RelationshipEngine(db_path=str(tmp_path / "relationships.db"))
    app = Flask(__name__)
    app.register_blueprint(create_relationship_blueprint(engine))
    return app.test_client(), engine


def test_relationship_mutations_fail_closed_without_admin_key(monkeypatch, tmp_path):
    monkeypatch.delenv("RELATIONSHIPS_ADMIN_KEY", raising=False)
    monkeypatch.delenv("RC_ADMIN_KEY", raising=False)
    client, engine = _build_client(tmp_path)

    for path, payload in MUTATING_ENDPOINTS:
        response = client.post(path, json=payload)

        assert response.status_code == 401
        assert engine.get_relationship("alice", "bob") is None


def test_relationship_mutations_reject_missing_or_wrong_admin_key(monkeypatch, tmp_path):
    monkeypatch.setenv("RELATIONSHIPS_ADMIN_KEY", "relationship-admin-secret")
    monkeypatch.delenv("RC_ADMIN_KEY", raising=False)
    client, engine = _build_client(tmp_path)

    for path, payload in MUTATING_ENDPOINTS:
        missing = client.post(path, json=payload)
        wrong = client.post(path, json=payload, headers={"X-Admin-Key": "wrong"})

        assert missing.status_code == 401
        assert wrong.status_code == 401
        assert engine.get_relationship("alice", "bob") is None


def test_relationship_mutations_accept_configured_admin_key(monkeypatch, tmp_path):
    monkeypatch.setenv("RELATIONSHIPS_ADMIN_KEY", "relationship-admin-secret")
    monkeypatch.delenv("RC_ADMIN_KEY", raising=False)
    client, engine = _build_client(tmp_path)
    engine.initialize_relationship("alice", "bob")

    response = client.post(
        "/api/relationships/alice/bob/disagree",
        json={"topic": "model routing"},
        headers={"X-Admin-Key": "relationship-admin-secret"},
    )

    assert response.status_code == 200
    relationship = engine.get_relationship("alice", "bob")
    assert relationship is not None
    assert relationship["disagreement_count"] == 1


def test_relationship_mutations_accept_legacy_api_key_header(monkeypatch, tmp_path):
    monkeypatch.setenv("RC_ADMIN_KEY", "legacy-admin-secret")
    monkeypatch.delenv("RELATIONSHIPS_ADMIN_KEY", raising=False)
    client, engine = _build_client(tmp_path)

    response = client.post(
        "/api/relationships/alice/bob/collaborate",
        json={"description": "shared runbook"},
        headers={"X-API-Key": "legacy-admin-secret"},
    )

    assert response.status_code == 200
    relationship = engine.get_relationship("alice", "bob")
    assert relationship is not None
    assert relationship["collaboration_count"] == 1


def test_relationship_mutations_reject_non_object_json(monkeypatch, tmp_path):
    monkeypatch.setenv("RELATIONSHIPS_ADMIN_KEY", "relationship-admin-secret")
    monkeypatch.delenv("RC_ADMIN_KEY", raising=False)
    client, engine = _build_client(tmp_path)

    for path, _payload in ALL_MUTATING_ENDPOINTS:
        response = client.post(
            path,
            headers={"X-Admin-Key": "relationship-admin-secret"},
            json=["not", "an", "object"],
        )

        assert response.status_code == 400
        assert response.get_json()["error"] == "JSON object expected"
        assert engine.get_relationship("alice", "bob") is None
