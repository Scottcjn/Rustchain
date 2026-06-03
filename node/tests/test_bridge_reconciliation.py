"""Tests for node/bridge_reconciliation.py (Layer 2 of federation arc)."""

from __future__ import annotations

import sqlite3
import sys
import time

import pytest
from flask import Flask

sys.path.insert(0, "node")

import bridge_api as ba  # noqa: E402
import bridge_federation_routes as fed  # noqa: E402
import bridge_reconciliation as rec  # noqa: E402


# ---------- fixtures --------------------------------------------------------


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    p = tmp_path / "reconciliation.db"
    with sqlite3.connect(p) as conn:
        ba.init_bridge_schema(conn.cursor())
        rec.init_reconciliation_schema(conn.cursor())
        conn.commit()
    monkeypatch.setenv("DB_PATH", str(p))
    return str(p)


@pytest.fixture
def app(db_path):
    a = Flask(__name__)
    a.config["TESTING"] = True
    fed.register_federation_routes(a)
    rec.register_reconciliation_routes(a)
    return a


@pytest.fixture
def client(app):
    return app.test_client()


def _seed_transfer(db_path, **overrides):
    """Insert one bridge_transfers row with sensible defaults."""
    now = int(time.time())
    row = {
        "direction": "deposit",
        "source_chain": "rustchain",
        "dest_chain": "ergo",
        "source_address": "miner_x",
        "dest_address": "ergo_x",
        "amount_i64": 1_000_000,
        "amount_rtc": 1.0,
        "bridge_type": "bottube",
        "bridge_fee_i64": 0,
        "external_tx_hash": None,
        "external_confirmations": 0,
        "required_confirmations": 12,
        "status": "pending",
        "lock_epoch": 1,
        "created_at": now,
        "updated_at": now,
        "tx_hash": f"h_{now}_{overrides.get('id_suffix', 0)}",
    }
    row.update({k: v for k, v in overrides.items() if k != "id_suffix"})
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO bridge_transfers (
                direction, source_chain, dest_chain,
                source_address, dest_address,
                amount_i64, amount_rtc, bridge_type, bridge_fee_i64,
                external_tx_hash, external_confirmations, required_confirmations,
                status, lock_epoch, created_at, updated_at, tx_hash
            ) VALUES (:direction, :source_chain, :dest_chain,
                      :source_address, :dest_address,
                      :amount_i64, :amount_rtc, :bridge_type, :bridge_fee_i64,
                      :external_tx_hash, :external_confirmations, :required_confirmations,
                      :status, :lock_epoch, :created_at, :updated_at, :tx_hash)
            """,
            row,
        )
        conn.commit()


# ---------- compute_state_hash determinism ----------------------------------


def test_state_hash_is_deterministic():
    state = {
        "locked_in_rtc": 10.0,
        "completed_in_rtc": 20.0,
        "voided_in_rtc": 0.0,
        "by_status": {"pending": {"count": 1, "total_rtc": 10.0}},
        "by_direction": {"deposit": {"count": 2, "total_rtc": 30.0}},
        "last_event_at": 12345,
        "computed_at": 99999,
    }
    h1 = rec.compute_state_hash(state)

    state2 = dict(state)
    state2["computed_at"] = 11111  # should be excluded from hash
    h2 = rec.compute_state_hash(state2)

    assert h1 == h2, "computed_at must not affect state_hash"
    assert len(h1) == 64, "sha-256 hex digest"


def test_state_hash_changes_with_underlying_state():
    state_a = {
        "locked_in_rtc": 10.0,
        "completed_in_rtc": 0.0,
        "voided_in_rtc": 0.0,
        "by_status": {},
        "by_direction": {},
        "last_event_at": 1,
        "computed_at": 0,
    }
    state_b = dict(state_a)
    state_b["locked_in_rtc"] = 10.0001
    assert rec.compute_state_hash(state_a) != rec.compute_state_hash(state_b)


# ---------- record_reconciliation_snapshot ----------------------------------


def test_snapshot_inserts_first_call(db_path):
    _seed_transfer(db_path, status="pending", amount_rtc=42.0)
    with sqlite3.connect(db_path) as conn:
        result = rec.record_reconciliation_snapshot(conn, epoch=7)
    assert result["created"] is True
    assert result["epoch"] == 7
    assert result["locked_in_rtc"] == 42.0
    assert result["bridged_supply_committed"] == 42.0
    assert result["relayer_signatures"] is None
    assert len(result["state_hash"]) == 64


def test_snapshot_is_idempotent_on_epoch(db_path):
    _seed_transfer(db_path, status="pending", amount_rtc=5.0)
    with sqlite3.connect(db_path) as conn:
        first = rec.record_reconciliation_snapshot(conn, epoch=10)
    # Now seed more activity — should NOT affect the snapshot for epoch 10
    _seed_transfer(db_path, status="completed", amount_rtc=999.0, id_suffix=999)
    with sqlite3.connect(db_path) as conn:
        second = rec.record_reconciliation_snapshot(conn, epoch=10)
    assert first["created"] is True
    assert second["created"] is False
    assert second["locked_in_rtc"] == 5.0  # unchanged
    assert second["state_hash"] == first["state_hash"]


def test_snapshot_bridged_supply_committed_formula(db_path):
    # locked = 10 + 20 = 30; completed = 50; voided = 3
    # bridged_supply_committed = 30 + 50 - 3 = 77
    _seed_transfer(db_path, status="pending", amount_rtc=10.0)
    _seed_transfer(db_path, status="locked", amount_rtc=20.0, id_suffix=1)
    _seed_transfer(db_path, status="completed", amount_rtc=50.0, id_suffix=2)
    _seed_transfer(db_path, status="voided", amount_rtc=3.0, id_suffix=3)
    with sqlite3.connect(db_path) as conn:
        snap = rec.record_reconciliation_snapshot(conn, epoch=42)
    assert snap["locked_in_rtc"] == 30.0
    assert snap["completed_in_rtc"] == 50.0
    assert snap["voided_in_rtc"] == 3.0
    assert snap["bridged_supply_committed"] == pytest.approx(77.0)


def test_snapshot_uses_provided_aggregate_state(db_path):
    """Caller can pass a pre-computed aggregate to avoid re-querying."""
    custom = {
        "locked_in_rtc": 1.0,
        "completed_in_rtc": 2.0,
        "voided_in_rtc": 0.5,
        "by_status": {},
        "by_direction": {},
        "last_event_at": 0,
        "computed_at": 12345,
    }
    with sqlite3.connect(db_path) as conn:
        snap = rec.record_reconciliation_snapshot(conn, epoch=1, aggregate_state=custom)
    assert snap["locked_in_rtc"] == 1.0
    assert snap["completed_in_rtc"] == 2.0
    assert snap["voided_in_rtc"] == 0.5
    assert snap["bridged_supply_committed"] == pytest.approx(2.5)


# ---------- routes ----------------------------------------------------------


def test_latest_with_no_snapshots(client):
    body = client.get("/bridge/reconciliation/latest").get_json()
    assert body == {"ok": True, "snapshot": None}


def test_latest_returns_highest_epoch(client, db_path):
    _seed_transfer(db_path, status="locked", amount_rtc=7.0)
    with sqlite3.connect(db_path) as conn:
        rec.record_reconciliation_snapshot(conn, epoch=1)
        rec.record_reconciliation_snapshot(conn, epoch=99)
        rec.record_reconciliation_snapshot(conn, epoch=50)
    body = client.get("/bridge/reconciliation/latest").get_json()
    assert body["snapshot"]["epoch"] == 99


def test_by_epoch_returns_specific_snapshot(client, db_path):
    _seed_transfer(db_path, status="pending", amount_rtc=4.0)
    with sqlite3.connect(db_path) as conn:
        rec.record_reconciliation_snapshot(conn, epoch=12)
    body = client.get("/bridge/reconciliation/by_epoch/12").get_json()
    assert body["snapshot"]["epoch"] == 12
    assert body["snapshot"]["locked_in_rtc"] == 4.0


def test_by_epoch_missing_returns_null(client, db_path):
    body = client.get("/bridge/reconciliation/by_epoch/777").get_json()
    assert body == {"ok": True, "snapshot": None}


def test_by_epoch_negative_returns_400(client):
    resp = client.get("/bridge/reconciliation/by_epoch/-1")
    # Flask's <int> converter rejects negatives at routing time, so the
    # explicit handler check is belt-and-suspenders. Either 404 or 400 OK.
    assert resp.status_code in (400, 404)


def test_recent_default_limit_and_descending_order(client, db_path):
    with sqlite3.connect(db_path) as conn:
        for e in [1, 5, 3, 9, 2]:
            rec.record_reconciliation_snapshot(conn, epoch=e)
    body = client.get("/bridge/reconciliation/recent").get_json()
    epochs = [s["epoch"] for s in body["snapshots"]]
    assert epochs == [9, 5, 3, 2, 1]
    assert body["count"] == 5
    assert body["limit"] == rec.DEFAULT_RECENT_LIMIT


def test_recent_limit_clamped_to_max(client, db_path):
    body = client.get(
        f"/bridge/reconciliation/recent?limit={rec.MAX_RECENT_LIMIT + 1000}"
    ).get_json()
    assert body["limit"] == rec.MAX_RECENT_LIMIT


def test_recent_invalid_limit_falls_back_to_default(client):
    body = client.get("/bridge/reconciliation/recent?limit=not_an_int").get_json()
    assert body["limit"] == rec.DEFAULT_RECENT_LIMIT


def test_recent_limit_clamped_to_one_minimum(client):
    body = client.get("/bridge/reconciliation/recent?limit=0").get_json()
    assert body["limit"] == 1


# ---------- public-no-auth ---------------------------------------------------


def test_all_routes_public_no_admin_key(client):
    paths = (
        "/bridge/reconciliation/latest",
        "/bridge/reconciliation/by_epoch/1",
        "/bridge/reconciliation/recent",
    )
    for p in paths:
        resp = client.get(p)
        assert resp.status_code == 200, f"{p} should not require admin key"
        # Bogus admin key must also not block
        resp = client.get(p, headers={"X-Admin-Key": "bogus"})
        assert resp.status_code == 200


# ---------- schema sanity ----------------------------------------------------


def test_schema_has_unique_epoch_constraint(db_path):
    with sqlite3.connect(db_path) as conn:
        rec.record_reconciliation_snapshot(conn, epoch=1)
        # Direct INSERT bypassing the function — must hit UNIQUE constraint.
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO bridge_reconciliation_snapshots ("
                "epoch, computed_at, locked_in_rtc, completed_in_rtc, "
                "voided_in_rtc, bridged_supply_committed, state_hash"
                ") VALUES (1, 0, 0.0, 0.0, 0.0, 0.0, 'x')"
            )
