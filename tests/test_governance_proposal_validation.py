# SPDX-License-Identifier: MIT

import sqlite3
import time

from flask import Flask

from node import governance


def _client(tmp_path, monkeypatch):
    db_path = tmp_path / "governance.db"
    governance.init_governance_tables(str(db_path))
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE attestations (miner_id TEXT, timestamp INTEGER)")
        conn.execute(
            "INSERT INTO attestations (miner_id, timestamp) VALUES (?, ?)",
            ("miner-1", int(time.time())),
        )
        conn.commit()

    monkeypatch.setattr(
        governance,
        "_verify_miner_signature",
        lambda miner_id, action, data: miner_id == "miner-1" and action == "propose",
    )

    app = Flask(__name__)
    app.register_blueprint(governance.create_governance_blueprint(str(db_path)))
    return app.test_client(), db_path


def _proposal_payload(**overrides):
    payload = {
        "miner_id": "miner-1",
        "title": "Tune quorum threshold",
        "description": "Adjust the quorum threshold after network review.",
        "proposal_type": "parameter_change",
        "parameter_key": "quorum_threshold",
        "parameter_value": "0.40",
        "timestamp": int(time.time()),
        "signature": "stubbed",
    }
    payload.update(overrides)
    return payload


def test_create_proposal_rejects_structured_parameter_value(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)

    response = client.post(
        "/api/governance/propose",
        json=_proposal_payload(parameter_value={"threshold": 0.40}),
    )

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "invalid_field_type",
        "field": "parameter_value",
        "expected": "string",
    }


def test_create_proposal_stores_string_parameter_value(tmp_path, monkeypatch):
    client, db_path = _client(tmp_path, monkeypatch)

    response = client.post(
        "/api/governance/propose",
        json=_proposal_payload(parameter_value=" 0.40 "),
    )

    assert response.status_code == 201
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT parameter_value FROM governance_proposals WHERE id = ?",
            (response.get_json()["proposal_id"],),
        ).fetchone()
    assert row[0] == "0.40"


def _seed_proposal_with_votes(db_path, vote_count=7):
    now = int(time.time())
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO governance_proposals (
                title, description, proposal_type, proposed_by,
                created_at, expires_at, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "Vote detail pagination",
                "Exercise the admin proposal detail votes slice.",
                "feature_activation",
                "miner-1",
                now,
                now + governance.VOTING_WINDOW_SECONDS,
                governance.STATUS_ACTIVE,
            ),
        )
        proposal_id = cursor.lastrowid
        for idx in range(vote_count):
            conn.execute(
                """
                INSERT INTO governance_votes (
                    proposal_id, miner_id, vote, weight, voted_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    proposal_id,
                    f"voter-{idx}",
                    "for" if idx % 2 == 0 else "against",
                    1.0,
                    now + idx,
                ),
            )
        conn.commit()
    return proposal_id


def test_get_proposal_detail_paginates_votes(tmp_path, monkeypatch):
    client, db_path = _client(tmp_path, monkeypatch)
    monkeypatch.setenv("RC_ADMIN_KEY", "test-admin")
    proposal_id = _seed_proposal_with_votes(db_path, vote_count=7)

    response = client.get(
        f"/api/governance/proposal/{proposal_id}?votes_limit=3&votes_offset=2",
        headers={"X-Admin-Key": "test-admin"},
    )

    assert response.status_code == 200
    data = response.get_json()
    assert len(data["votes"]) == 3
    assert data["votes_total"] == 7
    assert data["votes_limit"] == 3
    assert data["votes_offset"] == 2
    assert [vote["miner_id"] for vote in data["votes"]] == [
        "voter-4",
        "voter-3",
        "voter-2",
    ]


def test_get_proposal_detail_rejects_invalid_votes_offset(tmp_path, monkeypatch):
    client, db_path = _client(tmp_path, monkeypatch)
    monkeypatch.setenv("RC_ADMIN_KEY", "test-admin")
    proposal_id = _seed_proposal_with_votes(db_path, vote_count=1)

    response = client.get(
        f"/api/governance/proposal/{proposal_id}?votes_offset=abc",
        headers={"X-Admin-Key": "test-admin"},
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "votes_offset must be an integer"
