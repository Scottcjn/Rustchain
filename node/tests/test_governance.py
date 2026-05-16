"""
RIP-0002 Governance Test Suite
================================
Tests governance proposal creation, voting, lifecycle, quorum, and veto.

Run with:
    pytest tests/test_governance.py -v

Author: NOX Ventures
"""

import gc
import pytest
import sqlite3
import tempfile
import time
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from governance import (
    init_governance_tables,
    create_governance_blueprint,
    STATUS_ACTIVE, STATUS_PASSED, STATUS_FAILED, STATUS_EXPIRED, STATUS_VETOED,
    VOTING_WINDOW_SECONDS,
)
from flask import Flask


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_db():
    """Temporary SQLite database for each test."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    init_governance_tables(db_path)

    # Seed schema that governance references (miners, attestations)
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS miners (
                wallet_name TEXT PRIMARY KEY,
                antiquity_multiplier REAL DEFAULT 1.0
            );
            CREATE TABLE IF NOT EXISTS attestations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                miner_id TEXT NOT NULL,
                timestamp INTEGER NOT NULL
            );
        """)
    finally:
        conn.close()

    yield db_path
    gc.collect()
    os.unlink(db_path)


@pytest.fixture
def app(tmp_db):
    app = Flask(__name__)
    bp = create_governance_blueprint(tmp_db)
    app.register_blueprint(bp)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def active_miner(tmp_db):
    """Insert a test miner with recent attestation."""
    with sqlite3.connect(tmp_db) as conn:
        conn.execute("INSERT INTO miners VALUES ('alice', 2.5)")
        conn.execute("INSERT INTO attestations (miner_id, timestamp) VALUES ('alice', ?)",
                     (int(time.time()) - 3600,))
    return "alice"


@pytest.fixture
def second_miner(tmp_db):
    with sqlite3.connect(tmp_db) as conn:
        conn.execute("INSERT INTO miners VALUES ('bob', 1.0)")
        conn.execute("INSERT INTO attestations (miner_id, timestamp) VALUES ('bob', ?)",
                     (int(time.time()) - 3600,))
    return "bob"


# ---------------------------------------------------------------------------
# Scenario 1: Proposal creation
# ---------------------------------------------------------------------------

def test_create_proposal_success(client, active_miner):
    """Active miner can create a parameter_change proposal."""
    res = client.post("/api/governance/propose", json={
        "miner_id": active_miner,
        "title": "Increase epoch length to 200 slots",
        "description": "Longer epochs reduce overhead and improve finality guarantees.",
        "proposal_type": "parameter_change",
        "parameter_key": "epoch_length",
        "parameter_value": "200",
    })
    assert res.status_code == 201
    data = res.get_json()
    assert data["ok"] is True
    assert data["proposal_id"] == 1
    assert data["status"] == STATUS_ACTIVE
    assert "sophia_analysis" in data


def test_create_proposal_feature_activation(client, active_miner):
    """Feature activation proposal requires no parameter_key."""
    res = client.post("/api/governance/propose", json={
        "miner_id": active_miner,
        "title": "Activate RIP-0010 Dynamic Rewards",
        "description": "Enable dynamic reward scaling based on network participation.",
        "proposal_type": "feature_activation",
    })
    assert res.status_code == 201


def test_create_proposal_inactive_miner_rejected(client, tmp_db):
    """Inactive miner cannot create proposals."""
    with sqlite3.connect(tmp_db) as conn:
        conn.execute("INSERT INTO miners VALUES ('ghost', 1.0)")
        # No recent attestation

    res = client.post("/api/governance/propose", json={
        "miner_id": "ghost",
        "title": "Test",
        "description": "Should fail because miner is inactive.",
        "proposal_type": "feature_activation",
    })
    assert res.status_code == 403


def test_create_proposal_invalid_type_rejected(client, active_miner):
    """Invalid proposal type is rejected."""
    res = client.post("/api/governance/propose", json={
        "miner_id": active_miner,
        "title": "Bad proposal",
        "description": "This has an invalid type.",
        "proposal_type": "hack_the_chain",
    })
    assert res.status_code == 400


def test_create_proposal_missing_parameter_key(client, active_miner):
    """parameter_change without parameter_key is rejected."""
    res = client.post("/api/governance/propose", json={
        "miner_id": active_miner,
        "title": "Change something",
        "description": "Missing parameter_key.",
        "proposal_type": "parameter_change",
    })
    assert res.status_code == 400


def test_governance_write_routes_reject_non_object_json(client):
    """Governance write routes reject JSON arrays before field access."""
    propose = client.post("/api/governance/propose", json=["not", "an", "object"])
    assert propose.status_code == 400
    assert propose.get_json() == {"error": "invalid_json"}

    vote = client.post("/api/governance/vote", json=["not", "an", "object"])
    assert vote.status_code == 400
    assert vote.get_json() == {"error": "invalid_json"}

    veto = client.post("/api/governance/veto/1", json=["not", "an", "object"])
    assert veto.status_code == 400
    assert veto.get_json() == {"error": "invalid_json"}


def test_governance_write_routes_reject_malformed_field_types(client, active_miner):
    """Governance write routes reject malformed fields without server errors."""
    propose = client.post("/api/governance/propose", json={
        "miner_id": active_miner,
        "title": ["not", "a", "string"],
        "description": "Malformed title should be rejected.",
        "proposal_type": "feature_activation",
    })
    assert propose.status_code == 400
    assert propose.get_json() == {
        "error": "invalid_field_type",
        "field": "title",
        "expected": "string",
    }

    vote = client.post("/api/governance/vote", json={
        "miner_id": active_miner,
        "proposal_id": {"not": "an integer"},
        "vote": "for",
    })
    assert vote.status_code == 400
    assert vote.get_json() == {
        "error": "invalid_field_type",
        "field": "proposal_id",
        "expected": "integer",
    }

    veto = client.post("/api/governance/veto/1", json={
        "admin_key": ["not", "a", "string"],
        "reason": "Malformed admin key should be rejected.",
    })
    assert veto.status_code == 400
    assert veto.get_json() == {
        "error": "invalid_field_type",
        "field": "admin_key",
        "expected": "string",
    }


def test_governance_signature_field_type_returns_unauthorized(client, active_miner):
    """Malformed signature fields fail authentication instead of crashing."""
    res = client.post("/api/governance/propose", json={
        "miner_id": active_miner,
        "title": "Malformed signature",
        "description": "Signature is the wrong JSON type.",
        "proposal_type": "feature_activation",
        "signature": {"not": "a string"},
        "timestamp": int(time.time()),
    })
    assert res.status_code == 401


# ---------------------------------------------------------------------------
# Scenario 2: Voting
# ---------------------------------------------------------------------------

def test_vote_for_proposal(client, active_miner, second_miner, tmp_db):
    """Two miners can vote on a proposal."""
    # Create proposal
    res = client.post("/api/governance/propose", json={
        "miner_id": active_miner,
        "title": "Test proposal",
        "description": "Test voting.",
        "proposal_type": "feature_activation",
    })
    assert res.status_code == 201
    pid = res.get_json()["proposal_id"]

    # alice votes for
    res = client.post("/api/governance/vote", json={
        "miner_id": active_miner,
        "proposal_id": pid,
        "vote": "for",
    })
    assert res.status_code == 200
    assert res.get_json()["vote"] == "for"

    # bob votes against
    res = client.post("/api/governance/vote", json={
        "miner_id": second_miner,
        "proposal_id": pid,
        "vote": "against",
    })
    assert res.status_code == 200

    # Check results
    res = client.get(f"/api/governance/results/{pid}")
    data = res.get_json()
    assert data["votes_for"] == 2.5   # alice antiquity=2.5
    assert data["votes_against"] == 1.0  # bob antiquity=1.0


def test_vote_change_allowed(client, active_miner, tmp_db):
    """Miner can change their vote on an active proposal."""
    res = client.post("/api/governance/propose", json={
        "miner_id": active_miner,
        "title": "Changeable vote test",
        "description": "Miner changes mind.",
        "proposal_type": "emergency",
    })
    pid = res.get_json()["proposal_id"]

    client.post("/api/governance/vote", json={
        "miner_id": active_miner, "proposal_id": pid, "vote": "against"
    })
    client.post("/api/governance/vote", json={
        "miner_id": active_miner, "proposal_id": pid, "vote": "for"
    })

    res = client.get(f"/api/governance/results/{pid}")
    data = res.get_json()
    assert data["votes_for"] > 0
    assert data["votes_against"] == 0.0


def test_vote_on_nonexistent_proposal(client, active_miner):
    """Voting on a nonexistent proposal returns 404."""
    res = client.post("/api/governance/vote", json={
        "miner_id": active_miner,
        "proposal_id": 999,
        "vote": "for",
    })
    assert res.status_code == 404


def test_invalid_vote_choice(client, active_miner, tmp_db):
    """Invalid vote choice is rejected."""
    res = client.post("/api/governance/propose", json={
        "miner_id": active_miner,
        "title": "Vote validation test",
        "description": "Testing invalid vote.",
        "proposal_type": "feature_activation",
    })
    pid = res.get_json()["proposal_id"]

    res = client.post("/api/governance/vote", json={
        "miner_id": active_miner, "proposal_id": pid, "vote": "maybe"
    })
    assert res.status_code == 400


# ---------------------------------------------------------------------------
# Scenario 3: Proposal listing
# ---------------------------------------------------------------------------

def test_list_proposals_empty(client):
    """Empty proposals list returned as empty array."""
    res = client.get("/api/governance/proposals")
    assert res.status_code == 200
    data = res.get_json()
    assert data["proposals"] == []
    assert data["count"] == 0


def test_list_proposals_rejects_non_integer_limit(client):
    """Malformed pagination returns a client error instead of a 500."""
    res = client.get("/api/governance/proposals?limit=abc")

    assert res.status_code == 400
    assert res.get_json()["error"] == "limit must be an integer"


def test_list_proposals_rejects_negative_offset(client):
    """Negative offsets are invalid for proposal pagination."""
    res = client.get("/api/governance/proposals?offset=-1")

    assert res.status_code == 400
    assert res.get_json()["error"] == "offset must be non-negative"


def test_list_proposals_with_filter(client, active_miner, tmp_db):
    """Proposals can be filtered by status."""
    client.post("/api/governance/propose", json={
        "miner_id": active_miner,
        "title": "Active one",
        "description": "Still voting.",
        "proposal_type": "feature_activation",
    })
    res = client.get("/api/governance/proposals?status=active")
    assert res.status_code == 200
    assert res.get_json()["count"] == 1


# ---------------------------------------------------------------------------
# Scenario 4: Governance stats
# ---------------------------------------------------------------------------

def test_governance_stats(client, active_miner):
    """Stats endpoint returns correct counts."""
    res = client.get("/api/governance/stats")
    assert res.status_code == 200
    data = res.get_json()
    assert "proposal_counts" in data
    assert "active_miners" in data
    assert data["quorum_threshold_pct"] == 33.0
    assert data["voting_window_days"] == 7


# ---------------------------------------------------------------------------
# Scenario 5: Sophia AI evaluation
# ---------------------------------------------------------------------------

def test_sophia_evaluates_emergency_as_high_risk(client, active_miner):
    """Emergency proposals are flagged HIGH risk by Sophia."""
    res = client.post("/api/governance/propose", json={
        "miner_id": active_miner,
        "title": "Emergency halt mining",
        "description": "Pause all mining operations due to a critical bug.",
        "proposal_type": "emergency",
    })
    data = res.get_json()
    assert "HIGH" in data["sophia_analysis"]


def test_sophia_evaluates_normal_as_low_risk(client, active_miner):
    """Normal proposals should be LOW risk."""
    res = client.post("/api/governance/propose", json={
        "miner_id": active_miner,
        "title": "Update README documentation",
        "description": "Improve developer onboarding documentation quality.",
        "proposal_type": "feature_activation",
    })
    data = res.get_json()
    assert "LOW" in data["sophia_analysis"]


# ---------------------------------------------------------------------------
# Scenario 6: Proposal detail endpoint
# ---------------------------------------------------------------------------

def test_get_proposal_detail(client, active_miner):
    """Get proposal by ID returns full details."""
    res = client.post("/api/governance/propose", json={
        "miner_id": active_miner,
        "title": "Detail test",
        "description": "Test getting proposal details.",
        "proposal_type": "feature_activation",
    })
    pid = res.get_json()["proposal_id"]

    res = client.get(f"/api/governance/proposal/{pid}")
    assert res.status_code == 200
    data = res.get_json()
    assert data["id"] == pid
    assert data["proposed_by"] == active_miner
    assert "votes" in data
    assert "time_remaining_seconds" in data


def test_get_nonexistent_proposal(client):
    """Getting a nonexistent proposal returns 404."""
    res = client.get("/api/governance/proposal/999")
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# Scenario 7: Anti-spam / edge cases
# ---------------------------------------------------------------------------

def test_no_miner_id_returns_400(client):
    """Missing miner_id returns 400."""
    res = client.post("/api/governance/propose", json={
        "title": "No miner",
        "description": "Should fail.",
        "proposal_type": "feature_activation",
    })
    assert res.status_code == 400


def test_empty_title_rejected(client, active_miner):
    """Empty title is rejected."""
    res = client.post("/api/governance/propose", json={
        "miner_id": active_miner,
        "title": "",
        "description": "Has description but no title.",
        "proposal_type": "feature_activation",
    })
    assert res.status_code == 400


def test_abstain_vote(client, active_miner, tmp_db):
    """Miner can vote to abstain."""
    res = client.post("/api/governance/propose", json={
        "miner_id": active_miner,
        "title": "Abstain test",
        "description": "Testing abstain vote.",
        "proposal_type": "feature_activation",
    })
    pid = res.get_json()["proposal_id"]

    res = client.post("/api/governance/vote", json={
        "miner_id": active_miner,
        "proposal_id": pid,
        "vote": "abstain",
    })
    assert res.status_code == 200

    res = client.get(f"/api/governance/results/{pid}")
    data = res.get_json()
    assert data["votes_abstain"] > 0


def test_founder_veto_uses_constant_time_admin_key_compare(client, tmp_db, monkeypatch):
    """Founder veto checks the admin key through hmac.compare_digest."""
    monkeypatch.setenv("RUSTCHAIN_ADMIN_KEY", "founder-secret")
    calls = []

    def spy_compare_digest(provided, expected):
        calls.append((provided, expected))
        return provided == expected

    monkeypatch.setattr(sys.modules["governance"].hmac, "compare_digest", spy_compare_digest)

    now = int(time.time())
    with sqlite3.connect(tmp_db) as conn:
        cursor = conn.execute(
            """INSERT INTO governance_proposals
               (title, description, proposal_type, proposed_by, created_at, expires_at, status)
               VALUES (?,?,?,?,?,?,?)""",
            ("Veto auth test", "Exercise founder veto admin key validation.",
             "emergency", "alice", now, now + VOTING_WINDOW_SECONDS, STATUS_ACTIVE),
        )
        pid = cursor.lastrowid

    denied = client.post(f"/api/governance/veto/{pid}", json={
        "admin_key": "wrong-secret",
        "reason": "invalid key should be rejected",
    })
    assert denied.status_code == 403

    accepted = client.post(f"/api/governance/veto/{pid}", json={
        "admin_key": "founder-secret",
        "reason": "valid key should be accepted",
    })
    assert accepted.status_code == 200
    assert accepted.get_json()["status"] == STATUS_VETOED

    assert calls == [
        ("wrong-secret", "founder-secret"),
        ("founder-secret", "founder-secret"),
    ]
