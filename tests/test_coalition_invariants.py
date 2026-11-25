# SPDX-License-Identifier: MIT
"""Regression tests for coalition ban-bypass, expiry, and membership invariants."""

import sqlite3
import time

import pytest
from flask import Flask

from node.coalition import (
    COALITION_STATUS_DISSOLVED,
    MAX_DESCRIPTION_LEN,
    MEMBER_STATUS_ACTIVE,
    MEMBER_STATUS_BANNED,
    PROPOSAL_STATUS_EXPIRED,
    create_coalition_blueprint,
    init_coalition_tables,
)

ADMIN_KEY = "test-admin-key"
ADMIN_HEADERS = {"X-Admin-Key": ADMIN_KEY}


@pytest.fixture
def coalition_env(tmp_path, monkeypatch):
    db_path = str(tmp_path / "coalition.db")
    init_coalition_tables(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS miners (
                wallet_name TEXT PRIMARY KEY,
                rtc_balance REAL DEFAULT 1.0,
                antiquity_multiplier REAL DEFAULT 1.0
            );
            INSERT INTO miners VALUES ('alice', 100.0, 2.0);
            INSERT INTO miners VALUES ('bob', 10.0, 1.0);
            INSERT INTO miners VALUES ('carol', 20.0, 1.0);
            """
        )

    monkeypatch.setenv("RC_ADMIN_KEY", ADMIN_KEY)
    monkeypatch.setenv("RUSTCHAIN_TEST_ALLOW_UNSIGNED_COALITION_MINERS", "1")

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(create_coalition_blueprint(db_path))
    return app.test_client(), db_path


def _create_coalition(client, miner_id="alice", name="Alpha"):
    res = client.post(
        "/api/coalition/create",
        json={"miner_id": miner_id, "name": name, "description": "Valid description"},
    )
    assert res.status_code == 201
    return res.get_json()["coalition_id"]


def test_banned_member_cannot_self_unban_via_join(coalition_env):
    client, db_path = coalition_env
    cid = _create_coalition(client)

    join_res = client.post("/api/coalition/join", json={"miner_id": "bob", "coalition_id": cid})
    assert join_res.status_code == 200

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE coalition_members SET status = ? WHERE coalition_id = ? AND miner_id = ?",
            (MEMBER_STATUS_BANNED, cid, "bob"),
        )
        conn.commit()

    rejoin_res = client.post("/api/coalition/join", json={"miner_id": "bob", "coalition_id": cid})
    assert rejoin_res.status_code == 403
    assert "banned" in rejoin_res.get_json()["error"].lower()

    with sqlite3.connect(db_path) as conn:
        status = conn.execute(
            "SELECT status FROM coalition_members WHERE coalition_id = ? AND miner_id = ?",
            (cid, "bob"),
        ).fetchone()[0]
    assert status == MEMBER_STATUS_BANNED

    prop_res = client.post(
        "/api/coalition/propose",
        json={"miner_id": "bob", "coalition_id": cid, "title": "Sneak proposal"},
    )
    assert prop_res.status_code == 403


def test_left_member_can_still_rejoin(coalition_env):
    client, _ = coalition_env
    cid = _create_coalition(client)

    assert client.post("/api/coalition/join", json={"miner_id": "bob", "coalition_id": cid}).status_code == 200
    assert client.post("/api/coalition/leave", json={"miner_id": "bob", "coalition_id": cid}).status_code == 200

    rejoin_res = client.post("/api/coalition/join", json={"miner_id": "bob", "coalition_id": cid})
    assert rejoin_res.status_code == 200
    assert rejoin_res.get_json()["status"] == MEMBER_STATUS_ACTIVE


def test_dissolved_coalition_rejects_new_proposals_and_votes(coalition_env):
    client, db_path = coalition_env
    cid = _create_coalition(client)

    prop_res = client.post(
        "/api/coalition/propose",
        json={"miner_id": "alice", "coalition_id": cid, "title": "Pre-dissolve proposal"},
    )
    assert prop_res.status_code == 201
    pid = prop_res.get_json()["proposal_id"]

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE coalitions SET status = ? WHERE id = ?",
            (COALITION_STATUS_DISSOLVED, cid),
        )
        conn.commit()

    new_prop = client.post(
        "/api/coalition/propose",
        json={"miner_id": "alice", "coalition_id": cid, "title": "Post-dissolve proposal"},
    )
    assert new_prop.status_code == 404

    vote_res = client.post(
        "/api/coalition/vote",
        json={"miner_id": "alice", "proposal_id": pid, "vote": "for"},
    )
    assert vote_res.status_code == 409


def test_flamebound_review_rejects_expired_proposal(coalition_env):
    client, db_path = coalition_env
    cid = _create_coalition(client)

    prop_res = client.post(
        "/api/coalition/propose",
        json={"miner_id": "alice", "coalition_id": cid, "title": "Expired proposal"},
    )
    assert prop_res.status_code == 201
    pid = prop_res.get_json()["proposal_id"]

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE coalition_proposals SET expires_at = ? WHERE id = ?",
            (int(time.time()) - 60, pid),
        )
        conn.commit()

    review_res = client.post(
        "/api/coalition/flamebound-review",
        headers=ADMIN_HEADERS,
        json={"proposal_id": pid, "decision": "veto", "reason": "Too late"},
    )
    assert review_res.status_code == 409

    with sqlite3.connect(db_path) as conn:
        status = conn.execute(
            "SELECT status FROM coalition_proposals WHERE id = ?",
            (pid,),
        ).fetchone()[0]
        review_count = conn.execute(
            "SELECT COUNT(*) FROM flamebound_reviews WHERE proposal_id = ?",
            (pid,),
        ).fetchone()[0]
    assert status == PROPOSAL_STATUS_EXPIRED
    assert review_count == 0


def test_vote_rejects_proposal_at_exact_expiry_boundary(coalition_env, monkeypatch):
    client, db_path = coalition_env
    cid = _create_coalition(client)

    prop_res = client.post(
        "/api/coalition/propose",
        json={"miner_id": "alice", "coalition_id": cid, "title": "Boundary proposal"},
    )
    assert prop_res.status_code == 201
    pid = prop_res.get_json()["proposal_id"]

    expiry = int(time.time()) + 100
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE coalition_proposals SET expires_at = ? WHERE id = ?",
            (expiry, pid),
        )
        conn.commit()

    # First call (_settle_expired_proposals) sees expiry - 1; second call (cast_vote) hits exact expiry.
    ticks = iter([expiry - 1, expiry])
    monkeypatch.setattr("node.coalition.time.time", lambda: next(ticks, expiry))

    vote_res = client.post(
        "/api/coalition/vote",
        json={"miner_id": "alice", "proposal_id": pid, "vote": "for"},
    )
    assert vote_res.status_code == 409
    assert "voting window has closed" in vote_res.get_json()["error"].lower()


def test_description_and_reason_enforce_max_length(coalition_env):
    client, _ = coalition_env
    oversized = "x" * (MAX_DESCRIPTION_LEN + 1)

    create_res = client.post(
        "/api/coalition/create",
        json={"miner_id": "alice", "name": "TooLongDesc", "description": oversized},
    )
    assert create_res.status_code == 400

    cid = _create_coalition(client)
    propose_res = client.post(
        "/api/coalition/propose",
        json={"miner_id": "alice", "coalition_id": cid, "title": "Valid", "description": oversized},
    )
    assert propose_res.status_code == 400

    valid_prop = client.post(
        "/api/coalition/propose",
        json={"miner_id": "alice", "coalition_id": cid, "title": "Valid"},
    )
    assert valid_prop.status_code == 201
    pid = valid_prop.get_json()["proposal_id"]

    review_res = client.post(
        "/api/coalition/flamebound-review",
        headers=ADMIN_HEADERS,
        json={"proposal_id": pid, "decision": "approve", "reason": oversized},
    )
    assert review_res.status_code == 400


def test_get_coalition_member_count_excludes_left_and_banned(coalition_env):
    client, db_path = coalition_env
    cid = _create_coalition(client)

    assert client.post("/api/coalition/join", json={"miner_id": "bob", "coalition_id": cid}).status_code == 200
    assert client.post("/api/coalition/join", json={"miner_id": "carol", "coalition_id": cid}).status_code == 200
    assert client.post("/api/coalition/leave", json={"miner_id": "bob", "coalition_id": cid}).status_code == 200

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE coalition_members SET status = ? WHERE coalition_id = ? AND miner_id = ?",
            (MEMBER_STATUS_BANNED, cid, "carol"),
        )
        conn.commit()

    detail_res = client.get(f"/api/coalition/{cid}", headers=ADMIN_HEADERS)
    assert detail_res.status_code == 200
    detail = detail_res.get_json()
    assert detail["member_count"] == 1
    assert len(detail["members"]) == 3
