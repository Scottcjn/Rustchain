# SPDX-License-Identifier: MIT
"""Regression tests for governance atomic fee deduction, concurrency, and expiry invariants."""

import sqlite3
import threading
import time

import pytest
from flask import Flask

from node.governance import (
    MAX_DESCRIPTION_LEN,
    MAX_PROPOSALS_PER_MINER,
    PROPOSAL_FEE_RTC,
    STATUS_ACTIVE,
    STATUS_EXPIRED,
    STATUS_PASSED,
    _deduct_proposal_fee,
    _get_miner_antiquity_weight,
    _verify_miner_signature,
    create_governance_blueprint,
    init_governance_tables,
)

FOUNDER_KEY = "founder-test-secret"


@pytest.fixture
def governance_env(tmp_path, monkeypatch):
    db_path = str(tmp_path / "governance.db")
    init_governance_tables(db_path)
    now = int(time.time())
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS miners (
                wallet_name TEXT PRIMARY KEY,
                antiquity_multiplier REAL DEFAULT 1.0
            );
            CREATE TABLE IF NOT EXISTS attestations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                miner_id TEXT NOT NULL,
                timestamp INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS balances (
                miner_id TEXT PRIMARY KEY,
                amount_i64 INTEGER NOT NULL DEFAULT 0
            );
            """
        )
        conn.execute("INSERT INTO miners VALUES ('alice', 2.0)")
        conn.execute(
            "INSERT INTO attestations (miner_id, timestamp) VALUES ('alice', ?)",
            (now,),
        )
        conn.execute(
            "INSERT INTO balances (miner_id, amount_i64) VALUES ('alice', ?)",
            (PROPOSAL_FEE_RTC * 1_000_000,),
        )
        conn.commit()

    monkeypatch.setenv("RUSTCHAIN_ADMIN_KEY", FOUNDER_KEY)
    monkeypatch.setattr(
        "node.governance._verify_miner_signature",
        lambda miner_id, action, data: miner_id == "alice" and action in ("propose", "vote"),
    )

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(create_governance_blueprint(db_path))
    return app, db_path


def _proposal_payload(title="Atomic fee test"):
    return {
        "miner_id": "alice",
        "title": title,
        "description": "Regression test proposal description.",
        "proposal_type": "feature_activation",
        "timestamp": int(time.time()),
        "signature": "stubbed",
    }


def test_deduct_proposal_fee_refuses_overdraft_both_schemas():
    # Schema B: amount_i64
    with sqlite3.connect(":memory:") as conn_b:
        conn_b.execute("CREATE TABLE balances (miner_id TEXT PRIMARY KEY, amount_i64 INTEGER)")
        conn_b.execute("INSERT INTO balances VALUES ('alice', ?)", (5_000_000,))
        assert _deduct_proposal_fee(conn_b, "alice", 10.0) is False
        assert conn_b.execute("SELECT amount_i64 FROM balances WHERE miner_id = 'alice'").fetchone()[0] == 5_000_000

        conn_b.execute("UPDATE balances SET amount_i64 = ? WHERE miner_id = 'alice'", (10_000_000,))
        assert _deduct_proposal_fee(conn_b, "alice", 10.0) is True
        assert conn_b.execute("SELECT amount_i64 FROM balances WHERE miner_id = 'alice'").fetchone()[0] == 0
        assert _deduct_proposal_fee(conn_b, "alice", 10.0) is False
        assert conn_b.execute("SELECT amount_i64 FROM balances WHERE miner_id = 'alice'").fetchone()[0] == 0

    # Schema A: balance_rtc
    with sqlite3.connect(":memory:") as conn_a:
        conn_a.execute("CREATE TABLE balances (miner_pk TEXT PRIMARY KEY, balance_rtc REAL)")
        conn_a.execute("INSERT INTO balances VALUES ('alice', 5.0)")
        assert _deduct_proposal_fee(conn_a, "alice", 10.0) is False
        assert conn_a.execute("SELECT balance_rtc FROM balances WHERE miner_pk = 'alice'").fetchone()[0] == 5.0

        conn_a.execute("UPDATE balances SET balance_rtc = 10.0 WHERE miner_pk = 'alice'")
        assert _deduct_proposal_fee(conn_a, "alice", 10.0) is True
        assert conn_a.execute("SELECT balance_rtc FROM balances WHERE miner_pk = 'alice'").fetchone()[0] == 0.0
        assert _deduct_proposal_fee(conn_a, "alice", 10.0) is False
        assert _deduct_proposal_fee(conn_a, "alice", -1.0) is False
        assert _deduct_proposal_fee(conn_a, "alice", float("nan")) is False
        assert _deduct_proposal_fee(conn_a, "alice", float("inf")) is False
        assert _deduct_proposal_fee(conn_a, "alice", True) is False


def test_concurrent_propose_cannot_overdraft_balance(governance_env):
    app, db_path = governance_env
    workers = 6
    barrier = threading.Barrier(workers)
    statuses = []
    lock = threading.Lock()

    def submit(idx):
        client = app.test_client()
        barrier.wait(timeout=5)
        resp = client.post("/api/governance/propose", json=_proposal_payload(f"Race proposal {idx}"))
        with lock:
            statuses.append(resp.status_code)

    threads = [threading.Thread(target=submit, args=(i,)) for i in range(workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=15)

    assert statuses.count(201) == 1
    assert statuses.count(402) == workers - 1

    with sqlite3.connect(db_path) as conn:
        bal = conn.execute("SELECT amount_i64 FROM balances WHERE miner_id = 'alice'").fetchone()[0]
        count = conn.execute("SELECT COUNT(*) FROM governance_proposals").fetchone()[0]
    assert bal == 0
    assert count == 1


def test_concurrent_propose_enforces_max_active_proposals_without_overcharging(governance_env):
    app, db_path = governance_env
    now = int(time.time())
    starting_balance = 100 * 1_000_000
    with sqlite3.connect(db_path) as conn:
        conn.execute("UPDATE balances SET amount_i64 = ? WHERE miner_id = 'alice'", (starting_balance,))
        for i in range(MAX_PROPOSALS_PER_MINER - 1):
            conn.execute(
                """INSERT INTO governance_proposals
                   (title, description, proposal_type, proposed_by, created_at, expires_at, status)
                   VALUES (?,?,?,?,?,?,?)""",
                (f"Existing {i}", "desc", "feature_activation", "alice", now, now + 3600, STATUS_ACTIVE),
            )
        conn.commit()

    workers = 5
    barrier = threading.Barrier(workers)
    statuses = []
    lock = threading.Lock()

    def submit(idx):
        client = app.test_client()
        barrier.wait(timeout=5)
        resp = client.post("/api/governance/propose", json=_proposal_payload(f"Cap race {idx}"))
        with lock:
            statuses.append(resp.status_code)

    threads = [threading.Thread(target=submit, args=(i,)) for i in range(workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=15)

    assert statuses.count(201) == 1
    assert statuses.count(429) == workers - 1

    with sqlite3.connect(db_path) as conn:
        bal = conn.execute("SELECT amount_i64 FROM balances WHERE miner_id = 'alice'").fetchone()[0]
        count = conn.execute(
            "SELECT COUNT(*) FROM governance_proposals WHERE proposed_by = 'alice' AND status = ?",
            (STATUS_ACTIVE,),
        ).fetchone()[0]
    assert count == MAX_PROPOSALS_PER_MINER
    assert bal == starting_balance - PROPOSAL_FEE_RTC * 1_000_000


def test_founder_veto_rejects_expired_proposal_and_preserves_settled_status(governance_env):
    app, db_path = governance_env
    client = app.test_client()
    now = int(time.time())

    with sqlite3.connect(db_path) as conn:
        cur_passed = conn.execute(
            """INSERT INTO governance_proposals
               (title, description, proposal_type, proposed_by, created_at, expires_at, status, votes_for)
               VALUES (?,?,?,?,?,?,?,?)""",
            ("Already passed", "desc", "feature_activation", "alice", now - 7200, now - 60, STATUS_ACTIVE, 2.0),
        )
        passed_pid = cur_passed.lastrowid
        conn.execute(
            "INSERT INTO governance_votes (proposal_id, miner_id, vote, weight, voted_at) VALUES (?,?,?,?,?)",
            (passed_pid, "alice", "for", 2.0, now - 3600),
        )
        cur_expired = conn.execute(
            """INSERT INTO governance_proposals
               (title, description, proposal_type, proposed_by, created_at, expires_at, status)
               VALUES (?,?,?,?,?,?,?)""",
            ("Already expired", "desc", "feature_activation", "alice", now - 7200, now - 60, STATUS_ACTIVE),
        )
        expired_pid = cur_expired.lastrowid
        conn.commit()

    res_passed = client.post(
        f"/api/governance/veto/{passed_pid}",
        json={"admin_key": FOUNDER_KEY, "reason": "Too late to veto passed vote"},
    )
    assert res_passed.status_code == 409

    res_expired = client.post(
        f"/api/governance/veto/{expired_pid}",
        json={"admin_key": FOUNDER_KEY, "reason": "Too late to veto expired vote"},
    )
    assert res_expired.status_code == 409

    with sqlite3.connect(db_path) as conn:
        row_passed = conn.execute(
            "SELECT status, vetoed_by FROM governance_proposals WHERE id = ?",
            (passed_pid,),
        ).fetchone()
        row_expired = conn.execute(
            "SELECT status, vetoed_by FROM governance_proposals WHERE id = ?",
            (expired_pid,),
        ).fetchone()
    assert row_passed == (STATUS_PASSED, None)
    assert row_expired == (STATUS_EXPIRED, None)


def test_founder_veto_enforces_exact_expiry_boundary_and_reason_max_length(governance_env, monkeypatch):
    app, db_path = governance_env
    client = app.test_client()
    now = int(time.time())
    expiry = now + 100

    with sqlite3.connect(db_path) as conn:
        pid = conn.execute(
            """INSERT INTO governance_proposals
               (title, description, proposal_type, proposed_by, created_at, expires_at, status)
               VALUES (?,?,?,?,?,?,?)""",
            ("Boundary veto", "desc", "emergency", "alice", now, expiry, STATUS_ACTIVE),
        ).lastrowid
        conn.commit()

    oversized = client.post(
        f"/api/governance/veto/{pid}",
        json={"admin_key": FOUNDER_KEY, "reason": "r" * (MAX_DESCRIPTION_LEN + 1)},
    )
    assert oversized.status_code == 400

    # First call (_is_within_founder_veto_period) and second call (_settle_expired_proposals)
    # see expiry - 1; third call (founder_veto transaction) hits exact expiry.
    ticks = iter([expiry - 1, expiry - 1, expiry])
    monkeypatch.setattr("node.governance.time.time", lambda: next(ticks, expiry))

    boundary = client.post(
        f"/api/governance/veto/{pid}",
        json={"admin_key": FOUNDER_KEY, "reason": "Exact boundary veto"},
    )
    assert boundary.status_code == 409
    assert "voting window has closed" in boundary.get_json()["error"].lower()


def test_cast_vote_rejects_exact_expiry_boundary(governance_env, monkeypatch):
    app, db_path = governance_env
    client = app.test_client()
    now = int(time.time())
    expiry = now + 100

    with sqlite3.connect(db_path) as conn:
        pid = conn.execute(
            """INSERT INTO governance_proposals
               (title, description, proposal_type, proposed_by, created_at, expires_at, status)
               VALUES (?,?,?,?,?,?,?)""",
            ("Boundary vote", "desc", "feature_activation", "alice", now, expiry, STATUS_ACTIVE),
        ).lastrowid
        conn.commit()

    # Calls: 1) _settle_expired_proposals -> expiry - 1, 2) _is_active_miner -> expiry - 1,
    # 3) cast_vote now -> exact expiry.
    ticks = iter([expiry - 1, expiry - 1, expiry])
    monkeypatch.setattr("node.governance.time.time", lambda: next(ticks, expiry))

    vote_res = client.post(
        "/api/governance/vote",
        json={"miner_id": "alice", "proposal_id": pid, "vote": "for"},
    )
    assert vote_res.status_code == 409
    assert "voting window has closed" in vote_res.get_json()["error"].lower()


def test_non_finite_antiquity_weight_falls_back_to_one(tmp_path):
    db_path = str(tmp_path / "weights.db")
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE miners (wallet_name TEXT PRIMARY KEY, antiquity_multiplier REAL)")
        conn.execute("INSERT INTO miners VALUES ('null_miner', NULL)")
        conn.execute("INSERT INTO miners VALUES ('inf_miner', 9e999)")
        conn.execute("INSERT INTO miners VALUES ('neg_inf_miner', -9e999)")
        conn.execute("INSERT INTO miners VALUES ('nan_miner', 'nan')")
        conn.execute("INSERT INTO miners VALUES ('normal_miner', 2.5)")
        conn.commit()

    assert _get_miner_antiquity_weight("null_miner", db_path) == 1.0
    assert _get_miner_antiquity_weight("inf_miner", db_path) == 1.0
    assert _get_miner_antiquity_weight("neg_inf_miner", db_path) == 1.0
    assert _get_miner_antiquity_weight("nan_miner", db_path) == 1.0
    assert _get_miner_antiquity_weight("normal_miner", db_path) == 2.5


def test_verify_miner_signature_rejects_boolean_timestamp():
    assert _verify_miner_signature(
        "00" * 32,
        "propose",
        {"signature": "00" * 64, "timestamp": True},
    ) is False
