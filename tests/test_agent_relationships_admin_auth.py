# SPDX-License-Identifier: MIT

import sqlite3

import pytest
from flask import Flask

from agent_relationships import RelationshipEngine, create_relationship_blueprint


def _make_client(tmp_path):
    engine = RelationshipEngine(db_path=str(tmp_path / "relationships.db"))
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(create_relationship_blueprint(engine))
    return app.test_client(), engine


def _create_rivalry(engine):
    engine.initialize_relationship("alice", "bob")
    for topic in ("formats", "timing", "editing"):
        engine.record_disagreement("alice", "bob", topic)
    relationship = engine.get_relationship("alice", "bob")
    assert relationship["state"] == "rivals"
    return relationship


def _relationship_state(engine):
    relationship = engine.get_relationship("alice", "bob")
    return {
        "state": relationship["state"],
        "tension_level": relationship["tension_level"],
        "trust_level": relationship["trust_level"],
        "disagreement_count": relationship["disagreement_count"],
    }


def _intervention_count(engine):
    with sqlite3.connect(engine.db_path) as conn:
        return conn.execute("SELECT COUNT(*) FROM admin_interventions").fetchone()[0]


def test_intervention_fails_closed_when_admin_key_unconfigured(tmp_path, monkeypatch):
    client, engine = _make_client(tmp_path)
    _create_rivalry(engine)
    expected_state = _relationship_state(engine)
    monkeypatch.delenv("RELATIONSHIPS_ADMIN_KEY", raising=False)
    monkeypatch.delenv("RC_ADMIN_KEY", raising=False)

    response = client.post(
        "/api/relationships/alice/bob/intervene",
        json={"reason": "moderation reset"},
    )

    assert response.status_code == 401
    assert response.get_json()["error"] == "Relationship mutation admin key is not configured"
    assert _relationship_state(engine) == expected_state
    assert _intervention_count(engine) == 0


@pytest.mark.parametrize(
    "headers",
    [{}, {"X-Admin-Key": "wrong-admin-key"}, {"X-Admin-Key": "\u00e9"}],
)
def test_intervention_requires_valid_admin_key(tmp_path, monkeypatch, headers):
    client, engine = _make_client(tmp_path)
    _create_rivalry(engine)
    expected_state = _relationship_state(engine)
    monkeypatch.delenv("RELATIONSHIPS_ADMIN_KEY", raising=False)
    monkeypatch.setenv("RC_ADMIN_KEY", "expected-admin-key")

    response = client.post(
        "/api/relationships/alice/bob/intervene",
        headers=headers,
        json={"reason": "attacker reset"},
    )

    assert response.status_code == 401
    assert response.get_json()["error"] == "Unauthorized relationship mutation"
    assert _relationship_state(engine) == expected_state
    assert _intervention_count(engine) == 0


def test_intervention_accepts_valid_admin_key(tmp_path, monkeypatch):
    client, engine = _make_client(tmp_path)
    _create_rivalry(engine)
    monkeypatch.delenv("RELATIONSHIPS_ADMIN_KEY", raising=False)
    monkeypatch.setenv("RC_ADMIN_KEY", "expected-admin-key")

    response = client.post(
        "/api/relationships/alice/bob/intervene",
        headers={"X-Admin-Key": "expected-admin-key"},
        json={
            "admin_id": "ops",
            "reason": "moderation reset",
            "action": "reset_to_neutral",
        },
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert body["previous_state"] == "rivals"
    assert body["new_state"] == "neutral"
    assert _relationship_state(engine) == {
        "state": "neutral",
        "tension_level": 0,
        "trust_level": 50,
        "disagreement_count": 3,
    }
    assert _intervention_count(engine) == 1


def test_intervention_accepts_legacy_api_key_header(tmp_path, monkeypatch):
    client, engine = _make_client(tmp_path)
    _create_rivalry(engine)
    monkeypatch.delenv("RELATIONSHIPS_ADMIN_KEY", raising=False)
    monkeypatch.setenv("RC_ADMIN_KEY", "expected-admin-key")

    response = client.post(
        "/api/relationships/alice/bob/intervene",
        headers={"X-API-Key": "expected-admin-key"},
        json={"reason": "moderation reset"},
    )

    assert response.status_code == 200
    assert response.get_json()["new_state"] == "neutral"
    assert _intervention_count(engine) == 1
