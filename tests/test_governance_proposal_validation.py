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


def _fund_miner(db_path, balance_rtc=50):
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS balances (miner_id TEXT PRIMARY KEY, amount_i64 INTEGER DEFAULT 0)"
        )
        conn.execute(
            "INSERT OR REPLACE INTO balances (miner_id, amount_i64) VALUES (?, ?)",
            ("miner-1", int(balance_rtc * 1_000_000)),
        )
        conn.commit()


def _miner_balance_i64(db_path):
    with sqlite3.connect(db_path) as conn:
        return conn.execute(
            "SELECT amount_i64 FROM balances WHERE miner_id = ?",
            ("miner-1",),
        ).fetchone()[0]


def test_successful_create_proposal_charges_proposal_fee(tmp_path, monkeypatch):
    client, db_path = _client(tmp_path, monkeypatch)
    _fund_miner(db_path)

    response = client.post("/api/governance/propose", json=_proposal_payload())

    assert response.status_code == 201
    assert _miner_balance_i64(db_path) == 40_000_000


def test_max_active_proposal_rejection_does_not_charge_fee(tmp_path, monkeypatch):
    client, db_path = _client(tmp_path, monkeypatch)
    _fund_miner(db_path)
    now = int(time.time())
    with sqlite3.connect(db_path) as conn:
        for idx in range(governance.MAX_PROPOSALS_PER_MINER):
            conn.execute(
                """
                INSERT INTO governance_proposals (
                    title, description, proposal_type, proposed_by,
                    created_at, expires_at, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"Existing proposal {idx}",
                    "already active",
                    "feature_activation",
                    "miner-1",
                    now - idx,
                    now + governance.VOTING_WINDOW_SECONDS,
                    governance.STATUS_ACTIVE,
                ),
            )
        conn.commit()

    response = client.post("/api/governance/propose", json=_proposal_payload())

    assert response.status_code == 429
    assert response.get_json()["error"] == (
        f"Max {governance.MAX_PROPOSALS_PER_MINER} active proposals per miner"
    )
    assert _miner_balance_i64(db_path) == 50_000_000
