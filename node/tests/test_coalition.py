"""
RIP-0278 Agent Coalitions Governance Test Suite
=================================================
Tests coalition creation, membership management, proposal creation,
weighted voting, quorum/supermajority, and Sophia/Flamebound review.

Run with:
    pytest tests/test_coalition.py -v

Author: Claude (via Nous Hermes)
"""

import pytest
import gc
import sqlite3
import tempfile
import time
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from coalition import (
    init_coalition_tables,
    seed_flamebound_coalition,
    create_coalition_blueprint,
    COALITION_STATUS_ACTIVE, COALITION_STATUS_DISSOLVED,
    MEMBER_STATUS_ACTIVE, MEMBER_STATUS_LEFT,
    PROPOSAL_STATUS_ACTIVE, PROPOSAL_STATUS_PASSED, PROPOSAL_STATUS_FAILED,
    PROPOSAL_STATUS_EXPIRED, PROPOSAL_STATUS_VETOED,
    SUPERMAJORITY_THRESHOLD, QUORUM_THRESHOLD, PROPOSAL_WINDOW_SECONDS,
    FLAMEBUND_MINER_ID, FLAMEBUND_COALITION_NAME,
)
from flask import Flask

ADMIN_KEY = "test-admin-key"
ADMIN_HEADERS = {"X-Admin-Key": ADMIN_KEY}


def _unlink_temp_db(db_path):
    gc.collect()
    for _ in range(5):
        try:
            os.unlink(db_path)
            return
        except PermissionError:
            time.sleep(0.05)
    # Windows can keep Flask/SQLite test handles alive until process teardown.


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_db():
    """Temporary SQLite database for each test."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    init_coalition_tables(db_path)

    # Seed schema that coalition references (miners)
    with sqlite3.connect(db_path) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS miners (
                wallet_name TEXT PRIMARY KEY,
                rtc_balance REAL DEFAULT 1.0,
                antiquity_multiplier REAL DEFAULT 1.0
            );
        """)

    yield db_path
    _unlink_temp_db(db_path)


@pytest.fixture
def app(tmp_db, monkeypatch):
    monkeypatch.setenv("RC_ADMIN_KEY", ADMIN_KEY)
    app = Flask(__name__)
    bp = create_coalition_blueprint(tmp_db)
    app.register_blueprint(bp)
    app.config["TESTING"] = True
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def rich_miner(tmp_db):
    """Insert a test miner with balance and antiquity."""
    with sqlite3.connect(tmp_db) as conn:
        conn.execute("INSERT INTO miners VALUES ('alice', 100.0, 2.0)")
    return "alice"


@pytest.fixture
def poor_miner(tmp_db):
    """Insert a test miner with default weight."""
    with sqlite3.connect(tmp_db) as conn:
        conn.execute("INSERT INTO miners VALUES ('bob', 1.0, 1.0)")
    return "bob"


@pytest.fixture
def medium_miner(tmp_db):
    """Insert a test miner with moderate weight."""
    with sqlite3.connect(tmp_db) as conn:
        conn.execute("INSERT INTO miners VALUES ('charlie', 50.0, 1.5)")
    return "charlie"


@pytest.fixture
def test_coalition(client, rich_miner):
    """Create a coalition and return its id."""
    res = client.post("/api/coalition/create", json={
        "miner_id": rich_miner,
        "name": "Test Coalition",
        "description": "A coalition for testing purposes.",
    })
    assert res.status_code == 201
    return res.get_json()["coalition_id"]


# ---------------------------------------------------------------------------
# Scenario 1: Coalition Creation
# ---------------------------------------------------------------------------

def test_create_coalition_success(client, rich_miner):
    """Miner can create a coalition."""
    res = client.post("/api/coalition/create", json={
        "miner_id": rich_miner,
        "name": "Alpha Coalition",
        "description": "First coalition for testing.",
    })
    assert res.status_code == 201
    data = res.get_json()
    assert data["ok"] is True
    assert data["coalition_id"] == 2  # 1 is flamebound seed
    assert data["name"] == "Alpha Coalition"
    assert data["status"] == COALITION_STATUS_ACTIVE


def test_create_coalition_empty_name_rejected(client, rich_miner):
    """Empty name is rejected."""
    res = client.post("/api/coalition/create", json={
        "miner_id": rich_miner,
        "name": "",
        "description": "Should fail.",
    })
    assert res.status_code == 400


def test_create_coalition_no_miner_id_rejected(client):
    """Missing miner_id is rejected."""
    res = client.post("/api/coalition/create", json={
        "name": "No miner coalition",
    })
    assert res.status_code == 400


def test_create_coalition_creator_is_auto_member(client, rich_miner):
    """Creator should automatically be a member."""
    res = client.post("/api/coalition/create", json={
        "miner_id": rich_miner,
        "name": "Auto-Member Coalition",
        "description": "Creator should be auto-added.",
    })
    assert res.status_code == 201
    cid = res.get_json()["coalition_id"]

    res = client.get(f"/api/coalition/{cid}")
    data = res.get_json()
    members = data["members"]
    assert len(members) == 1
    assert members[0]["miner_id"] == rich_miner
    assert members[0]["status"] == MEMBER_STATUS_ACTIVE


def test_flamebound_seeded_on_blueprint_creation(app, tmp_db):
    """Sophia/The Flamebound coalition is auto-seeded."""
    with sqlite3.connect(tmp_db) as conn:
        row = conn.execute(
            "SELECT id, name, creator FROM coalitions WHERE name = ?",
            (FLAMEBUND_COALITION_NAME,)
        ).fetchone()
    assert row is not None
    assert row[1] == FLAMEBUND_COALITION_NAME
    assert row[2] == FLAMEBUND_MINER_ID


# ---------------------------------------------------------------------------
# Scenario 2: Membership Management
# ---------------------------------------------------------------------------

def test_join_coalition_success(client, test_coalition, poor_miner):
    """Miner can join an existing coalition."""
    res = client.post("/api/coalition/join", json={
        "miner_id": poor_miner,
        "coalition_id": test_coalition,
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data["ok"] is True
    assert data["coalition_id"] == test_coalition


def test_join_nonexistent_coalition_rejected(client, rich_miner):
    """Joining a non-existent coalition is rejected."""
    res = client.post("/api/coalition/join", json={
        "miner_id": rich_miner,
        "coalition_id": 99999,
    })
    assert res.status_code == 404


def test_join_already_member_rejected(client, test_coalition, rich_miner):
    """Already a member cannot re-join."""
    res = client.post("/api/coalition/join", json={
        "miner_id": rich_miner,
        "coalition_id": test_coalition,
    })
    assert res.status_code == 409


def test_leave_coalition_success(client, test_coalition, poor_miner):
    """Miner can leave a coalition."""
    # First join
    res = client.post("/api/coalition/join", json={
        "miner_id": poor_miner,
        "coalition_id": test_coalition,
    })
    assert res.status_code == 200

    # Then leave
    res = client.post("/api/coalition/leave", json={
        "miner_id": poor_miner,
        "coalition_id": test_coalition,
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == MEMBER_STATUS_LEFT


def test_leave_non_member_rejected(client, test_coalition, medium_miner):
    """Non-member cannot leave."""
    res = client.post("/api/coalition/leave", json={
        "miner_id": medium_miner,
        "coalition_id": test_coalition,
    })
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# Scenario 3: Proposal Creation
# ---------------------------------------------------------------------------

def test_create_proposal_success(client, test_coalition, rich_miner):
    """Active member can create a proposal."""
    res = client.post("/api/coalition/propose", json={
        "miner_id": rich_miner,
        "coalition_id": test_coalition,
        "title": "RIP-101: Increase reward multiplier",
        "description": "Proposing to increase the reward multiplier for long-term miners.",
        "rip_number": 101,
    })
    assert res.status_code == 201
    data = res.get_json()
    assert data["ok"] is True
    assert data["title"] == "RIP-101: Increase reward multiplier"
    assert data["status"] == PROPOSAL_STATUS_ACTIVE


def test_create_proposal_non_member_rejected(client, test_coalition, poor_miner):
    """Non-member cannot create proposals."""
    res = client.post("/api/coalition/propose", json={
        "miner_id": poor_miner,
        "coalition_id": test_coalition,
        "title": "Unauthorized proposal",
        "description": "Should fail.",
    })
    assert res.status_code == 403


def test_create_proposal_empty_title_rejected(client, test_coalition, rich_miner):
    """Empty title is rejected."""
    res = client.post("/api/coalition/propose", json={
        "miner_id": rich_miner,
        "coalition_id": test_coalition,
        "title": "",
        "description": "No title.",
    })
    assert res.status_code == 400


# ---------------------------------------------------------------------------
# Scenario 4: Voting (Weighted)
# ---------------------------------------------------------------------------

def _create_proposal_and_add_members(client, test_coalition, tmp_db, rich_miner, poor_miner, medium_miner):
    """Helper: add members and create a proposal."""
    # Add members
    for miner in [poor_miner, medium_miner]:
        res = client.post("/api/coalition/join", json={
            "miner_id": miner,
            "coalition_id": test_coalition,
        })
        assert res.status_code == 200

    # Create proposal
    res = client.post("/api/coalition/propose", json={
        "miner_id": rich_miner,
        "coalition_id": test_coalition,
        "title": "Test proposal for voting",
        "description": "Testing weighted voting.",
    })
    assert res.status_code == 201
    return res.get_json()["proposal_id"]


def test_vote_weighted_rich_miner(client, test_coalition, tmp_db, rich_miner, poor_miner, medium_miner):
    """Rich miner's vote weight = rtc_balance * antiquity_multiplier."""
    pid = _create_proposal_and_add_members(client, test_coalition, tmp_db, rich_miner, poor_miner, medium_miner)

    res = client.post("/api/coalition/vote", json={
        "miner_id": rich_miner,
        "proposal_id": pid,
        "vote": "for",
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data["weight"] == 200.0  # 100 * 2.0


def test_vote_weighted_poor_miner(client, test_coalition, tmp_db, rich_miner, poor_miner, medium_miner):
    """Poor miner's vote weight = 1.0 * 1.0 = 1.0."""
    pid = _create_proposal_and_add_members(client, test_coalition, tmp_db, rich_miner, poor_miner, medium_miner)

    res = client.post("/api/coalition/vote", json={
        "miner_id": poor_miner,
        "proposal_id": pid,
        "vote": "for",
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data["weight"] == 1.0  # 1.0 * 1.0


def test_vote_non_member_rejected(client, test_coalition, tmp_db, rich_miner, medium_miner):
    """Non-member cannot vote."""
    # Add only medium_miner; do NOT add "unknown"
    res = client.post("/api/coalition/join", json={
        "miner_id": medium_miner,
        "coalition_id": test_coalition,
    })
    assert res.status_code == 200

    # Create proposal
    res = client.post("/api/coalition/propose", json={
        "miner_id": rich_miner,
        "coalition_id": test_coalition,
        "title": "Test proposal for voting",
        "description": "Testing non-member rejection.",
    })
    assert res.status_code == 201
    pid = res.get_json()["proposal_id"]

    res = client.post("/api/coalition/vote", json={
        "miner_id": "unknown",
        "proposal_id": pid,
        "vote": "for",
    })
    assert res.status_code == 403


def test_vote_invalid_choice_rejected(client, test_coalition, tmp_db, rich_miner, poor_miner, medium_miner):
    """Invalid vote choice is rejected."""
    pid = _create_proposal_and_add_members(client, test_coalition, tmp_db, rich_miner, poor_miner, medium_miner)

    res = client.post("/api/coalition/vote", json={
        "miner_id": rich_miner,
        "proposal_id": pid,
        "vote": "abstain",  # abstain not allowed in coalition voting
    })
    assert res.status_code == 400


def test_vote_nonexistent_proposal_rejected(client, rich_miner):
    """Voting on non-existent proposal is rejected."""
    res = client.post("/api/coalition/vote", json={
        "miner_id": rich_miner,
        "proposal_id": 99999,
        "vote": "for",
    })
    assert res.status_code == 404


def test_change_vote(client, test_coalition, tmp_db, rich_miner, poor_miner, medium_miner):
    """Miner can change their vote."""
    pid = _create_proposal_and_add_members(client, test_coalition, tmp_db, rich_miner, poor_miner, medium_miner)

    # Vote for
    res = client.post("/api/coalition/vote", json={
        "miner_id": rich_miner,
        "proposal_id": pid,
        "vote": "for",
    })
    assert res.status_code == 200

    # Change to against
    res = client.post("/api/coalition/vote", json={
        "miner_id": rich_miner,
        "proposal_id": pid,
        "vote": "against",
    })
    assert res.status_code == 200

    # Check proposal tally
    res = client.get(f"/api/coalition/{test_coalition}/proposals")
    data = res.get_json()
    prop = data["proposals"][0]
    assert prop["votes_for"] == 0.0
    assert prop["votes_against"] == 200.0


# ---------------------------------------------------------------------------
# Scenario 5: Quorum & Supermajority
# ---------------------------------------------------------------------------

def test_supermajority_pass(client, test_coalition, tmp_db, rich_miner, poor_miner, medium_miner):
    """Proposal passes with 66%+ supermajority and 50%+ quorum."""
    pid = _create_proposal_and_add_members(client, test_coalition, tmp_db, rich_miner, poor_miner, medium_miner)

    # 3 members, need 50% quorum = at least 1.5 members voting (2)
    # rich votes for (weight=200), medium votes for (weight=75)
    res = client.post("/api/coalition/vote", json={
        "miner_id": rich_miner,
        "proposal_id": pid,
        "vote": "for",
    })
    assert res.status_code == 200

    res = client.post("/api/coalition/vote", json={
        "miner_id": medium_miner,
        "proposal_id": pid,
        "vote": "for",
    })
    assert res.status_code == 200

    # After vote, check quorum/supermajority flags
    data = res.get_json()
    assert data["quorum_met"] is True  # 2 out of 3 = 66.7% >= 50%
    assert data["supermajority_reached"] is True  # 275/275 = 100% >= 66%


def test_lack_of_quorum(client, test_coalition, tmp_db, rich_miner, poor_miner, medium_miner):
    """Proposal fails when quorum is not met."""
    pid = _create_proposal_and_add_members(client, test_coalition, tmp_db, rich_miner, poor_miner, medium_miner)

    # Only 1 out of 3 votes — below 50% quorum
    res = client.post("/api/coalition/vote", json={
        "miner_id": rich_miner,
        "proposal_id": pid,
        "vote": "for",
    })
    assert res.status_code == 200
    data = res.get_json()
    # 1/3 = 33% < 50% quorum
    assert data["quorum_met"] is False


def test_failed_due_to_not_supermajority(client, test_coalition, tmp_db, rich_miner, poor_miner, medium_miner):
    """Proposal fails when supermajority not reached."""
    pid = _create_proposal_and_add_members(client, test_coalition, tmp_db, rich_miner, poor_miner, medium_miner)

    # All 3 vote but split: rich=for, poor=against, medium=against
    # for=200, against=76 → 200/276 = 72% → supermajority reached
    # Let's make it fail: rich=for, poor=for, medium=against
    # for=201, against=75 → 201/276 = 72.8% → passes
    # Actually with these weights it will pass. Let's use a different scenario.

    # For this test, we verify the logic: if for/total < 66%, it fails
    # We'll vote for AND against to get a split
    client.post("/api/coalition/vote", json={
        "miner_id": poor_miner,
        "proposal_id": pid,
        "vote": "for",
    })
    client.post("/api/coalition/vote", json={
        "miner_id": medium_miner,
        "proposal_id": pid,
        "vote": "against",
    })

    res = client.post("/api/coalition/vote", json={
        "miner_id": rich_miner,
        "proposal_id": pid,
        "vote": "against",
    })
    data = res.get_json()
    # for=1, against=275 → 1/276 = 0.36% → not supermajority
    assert data["supermajority_reached"] is False


# ---------------------------------------------------------------------------
# Scenario 6: Sophia/Flamebound Review
# ---------------------------------------------------------------------------

def test_flamebound_approve(client, test_coalition, tmp_db, rich_miner, poor_miner, medium_miner):
    """Sophia can approve a proposal."""
    pid = _create_proposal_and_add_members(client, test_coalition, tmp_db, rich_miner, poor_miner, medium_miner)

    res = client.post(
        "/api/coalition/flamebound-review",
        headers=ADMIN_HEADERS,
        json={
            "proposal_id": pid,
            "decision": "approve",
            "reason": "Proposal is well-structured and aligns with protocol goals.",
        },
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["decision"] == "approve"
    assert data["proposal_status"] == PROPOSAL_STATUS_ACTIVE  # approved but still active


def test_flamebound_veto(client, test_coalition, tmp_db, rich_miner, poor_miner, medium_miner):
    """Sophia can veto a proposal."""
    pid = _create_proposal_and_add_members(client, test_coalition, tmp_db, rich_miner, poor_miner, medium_miner)

    res = client.post(
        "/api/coalition/flamebound-review",
        headers=ADMIN_HEADERS,
        json={
            "proposal_id": pid,
            "decision": "veto",
            "reason": "Proposal contains security risks.",
        },
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["decision"] == "veto"
    assert data["proposal_status"] == PROPOSAL_STATUS_VETOED


def test_flamebound_veto_prevents_voting(client, test_coalition, tmp_db, rich_miner, poor_miner, medium_miner):
    """After veto, further voting is rejected."""
    pid = _create_proposal_and_add_members(client, test_coalition, tmp_db, rich_miner, poor_miner, medium_miner)

    # Veto first
    res = client.post(
        "/api/coalition/flamebound-review",
        headers=ADMIN_HEADERS,
        json={
            "proposal_id": pid,
            "decision": "veto",
            "reason": "Security risk.",
        },
    )
    assert res.status_code == 200

    # Vote on vetoed proposal should fail
    res = client.post("/api/coalition/vote", json={
        "miner_id": rich_miner,
        "proposal_id": pid,
        "vote": "for",
    })
    assert res.status_code == 409


def test_flamebound_invalid_decision_rejected(client, test_coalition, tmp_db, rich_miner, poor_miner, medium_miner):
    """Invalid decision is rejected."""
    pid = _create_proposal_and_add_members(client, test_coalition, tmp_db, rich_miner, poor_miner, medium_miner)

    res = client.post(
        "/api/coalition/flamebound-review",
        headers=ADMIN_HEADERS,
        json={
            "proposal_id": pid,
            "decision": "maybe",
            "reason": "Unclear.",
        },
    )
    assert res.status_code == 400


def test_flamebound_nonexistent_proposal_rejected(client, rich_miner):
    """Review on non-existent proposal is rejected."""
    res = client.post(
        "/api/coalition/flamebound-review",
        headers=ADMIN_HEADERS,
        json={
            "proposal_id": 99999,
            "decision": "approve",
            "reason": "N/A",
        },
    )
    assert res.status_code == 404


def test_flamebound_review_rejects_unauthenticated_veto(client, test_coalition, tmp_db, rich_miner, poor_miner, medium_miner):
    """Unauthenticated callers cannot veto coalition proposals."""
    pid = _create_proposal_and_add_members(client, test_coalition, tmp_db, rich_miner, poor_miner, medium_miner)

    res = client.post("/api/coalition/flamebound-review", json={
        "proposal_id": pid,
        "decision": "veto",
        "reason": "attacker veto",
    })

    assert res.status_code == 401
    with sqlite3.connect(tmp_db) as conn:
        status = conn.execute(
            "SELECT status FROM coalition_proposals WHERE id = ?",
            (pid,),
        ).fetchone()[0]
        review_count = conn.execute(
            "SELECT COUNT(*) FROM flamebound_reviews WHERE proposal_id = ?",
            (pid,),
        ).fetchone()[0]

    assert status == PROPOSAL_STATUS_ACTIVE
    assert review_count == 0


def test_flamebound_review_fails_closed_without_admin_key(client, monkeypatch, test_coalition, tmp_db, rich_miner, poor_miner, medium_miner):
    """Flamebound review is disabled when RC_ADMIN_KEY is not configured."""
    pid = _create_proposal_and_add_members(client, test_coalition, tmp_db, rich_miner, poor_miner, medium_miner)
    monkeypatch.delenv("RC_ADMIN_KEY", raising=False)

    res = client.post(
        "/api/coalition/flamebound-review",
        headers=ADMIN_HEADERS,
        json={
            "proposal_id": pid,
            "decision": "approve",
            "reason": "N/A",
        },
    )

    assert res.status_code == 503


# ---------------------------------------------------------------------------
# Scenario 7: List & Get Coalitions
# ---------------------------------------------------------------------------

def test_list_coalitions_includes_flamebound(client):
    """List endpoint returns coalitions including Flamebound."""
    res = client.get("/api/coalition/list")
    assert res.status_code == 200
    data = res.get_json()
    assert data["count"] >= 1
    names = [c["name"] for c in data["coalitions"]]
    assert FLAMEBUND_COALITION_NAME in names


def test_list_coalitions_with_status_filter(client, rich_miner):
    """List can filter by status."""
    # Create a coalition
    client.post("/api/coalition/create", json={
        "miner_id": rich_miner,
        "name": "Active Coalition",
        "description": "For filtering test.",
    })

    res = client.get("/api/coalition/list?status=active")
    assert res.status_code == 200
    data = res.get_json()
    for c in data["coalitions"]:
        assert c["status"] == COALITION_STATUS_ACTIVE


def test_list_coalitions_rejects_non_integer_pagination(client):
    """Malformed pagination returns 400 instead of an internal error."""
    res = client.get("/api/coalition/list?limit=not-an-int")
    assert res.status_code == 400
    assert res.get_json() == {"error": "limit must be an integer"}

    res = client.get("/api/coalition/list?offset=not-an-int")
    assert res.status_code == 400
    assert res.get_json() == {"error": "offset must be an integer"}


def test_list_coalitions_rejects_negative_pagination(client):
    """Negative pagination values are invalid."""
    res = client.get("/api/coalition/list?limit=-5")
    assert res.status_code == 400
    assert res.get_json() == {"error": "limit must be at least 1"}

    res = client.get("/api/coalition/list?offset=-10")
    assert res.status_code == 400
    assert res.get_json() == {"error": "offset must be at least 0"}


def test_get_coalition_details(client, test_coalition, rich_miner, poor_miner):
    """Get coalition details with members."""
    # Add a member
    client.post("/api/coalition/join", json={
        "miner_id": poor_miner,
        "coalition_id": test_coalition,
    })

    res = client.get(f"/api/coalition/{test_coalition}")
    assert res.status_code == 200
    data = res.get_json()
    assert data["name"] == "Test Coalition"
    assert data["member_count"] == 2  # creator + poor_miner
    assert "members" in data


def test_get_nonexistent_coalition(client):
    """Get non-existent coalition returns 404."""
    res = client.get("/api/coalition/99999")
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# Scenario 8: Coalition Proposals Listing
# ---------------------------------------------------------------------------

def test_list_coalition_proposals(client, test_coalition, rich_miner, poor_miner):
    """List proposals for a coalition."""
    # Create a proposal
    client.post("/api/coalition/propose", json={
        "miner_id": rich_miner,
        "coalition_id": test_coalition,
        "title": "First proposal",
        "description": "Testing.",
    })

    res = client.get(f"/api/coalition/{test_coalition}/proposals")
    assert res.status_code == 200
    data = res.get_json()
    assert data["coalition_id"] == test_coalition
    assert data["count"] == 1
    assert data["proposals"][0]["title"] == "First proposal"


def test_list_proposals_status_filter(client, test_coalition, rich_miner):
    """List proposals can filter by status."""
    client.post("/api/coalition/propose", json={
        "miner_id": rich_miner,
        "coalition_id": test_coalition,
        "title": "Active proposal",
        "description": "Testing.",
    })

    res = client.get(f"/api/coalition/{test_coalition}/proposals?status=active")
    assert res.status_code == 200
    data = res.get_json()
    assert data["count"] == 1


def test_list_proposals_rejects_non_integer_pagination(client, test_coalition):
    """Proposal listing validates pagination before querying SQLite."""
    res = client.get(f"/api/coalition/{test_coalition}/proposals?limit=NaN")
    assert res.status_code == 400
    assert res.get_json() == {"error": "limit must be an integer"}

    res = client.get(f"/api/coalition/{test_coalition}/proposals?offset=NaN")
    assert res.status_code == 400
    assert res.get_json() == {"error": "offset must be an integer"}


def test_list_proposals_rejects_negative_pagination(client, test_coalition):
    """Proposal listing rejects negative pagination before querying SQLite."""
    res = client.get(f"/api/coalition/{test_coalition}/proposals?limit=-1")
    assert res.status_code == 400
    assert res.get_json() == {"error": "limit must be at least 1"}

    res = client.get(f"/api/coalition/{test_coalition}/proposals?offset=-1")
    assert res.status_code == 400
    assert res.get_json() == {"error": "offset must be at least 0"}


def test_list_proposals_nonexistent_coalition(client, rich_miner):
    """List proposals for non-existent coalition returns 404."""
    res = client.get("/api/coalition/99999/proposals")
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# Scenario 9: Statistics
# ---------------------------------------------------------------------------

def test_coalition_stats(client):
    """Stats endpoint returns aggregated data."""
    res = client.get("/api/coalition/stats")
    assert res.status_code == 200
    data = res.get_json()
    assert "coalition_counts" in data
    assert "proposal_counts" in data
    assert "total_votes_cast" in data
    assert "supermajority_threshold_pct" in data
    assert data["supermajority_threshold_pct"] == 66.0
    assert data["quorum_threshold_pct"] == 50.0
    assert data["proposal_window_days"] == 7


def test_stats_reflect_created_coalition(client, rich_miner):
    """Stats reflect newly created coalitions."""
    # Initial stats
    res1 = client.get("/api/coalition/stats")
    initial = res1.get_json()["coalition_counts"]["coalitions_active"]

    client.post("/api/coalition/create", json={
        "miner_id": rich_miner,
        "name": "Stats Test Coalition",
        "description": "For stats verification.",
    })

    res2 = client.get("/api/coalition/stats")
    final = res2.get_json()["coalition_counts"]["coalitions_active"]
    assert final == initial + 1


# ---------------------------------------------------------------------------
# Scenario 10: Edge Cases
# ---------------------------------------------------------------------------

def test_duplicate_flamebound_seed(tmp_db):
    """Calling seed_flamebound_coalition twice does not create duplicates."""
    id1 = seed_flamebound_coalition(tmp_db)
    id2 = seed_flamebound_coalition(tmp_db)
    assert id1 == id2

    with sqlite3.connect(tmp_db) as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM coalitions WHERE name = ?",
            (FLAMEBUND_COALITION_NAME,)
        ).fetchone()[0]
    assert count == 1


def test_proposal_tally_accuracy(client, test_coalition, tmp_db, rich_miner, poor_miner, medium_miner):
    """Vote tallies are accurately tracked."""
    pid = _create_proposal_and_add_members(client, test_coalition, tmp_db, rich_miner, poor_miner, medium_miner)

    # All vote for
    client.post("/api/coalition/vote", json={
        "miner_id": rich_miner, "proposal_id": pid, "vote": "for",
    })
    client.post("/api/coalition/vote", json={
        "miner_id": poor_miner, "proposal_id": pid, "vote": "for",
    })
    client.post("/api/coalition/vote", json={
        "miner_id": medium_miner, "proposal_id": pid, "vote": "for",
    })

    # Check proposal
    res = client.get(f"/api/coalition/{test_coalition}/proposals")
    data = res.get_json()
    prop = data["proposals"][0]
    # 200 + 1 + 75 = 276
    assert prop["votes_for"] == 276.0
    assert prop["votes_against"] == 0.0
