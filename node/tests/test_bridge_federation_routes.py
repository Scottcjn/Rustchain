"""Tests for node/bridge_federation_routes.py — public read-only federation routes."""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
import time

import pytest
from flask import Flask

sys.path.insert(0, "node")

import bridge_api as ba  # noqa: E402
import bridge_federation_routes as fed  # noqa: E402


# ---------- fixtures ---------------------------------------------------------


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    """Fresh sqlite db with bridge_transfers schema initialized."""
    p = tmp_path / "fed_routes.db"
    with sqlite3.connect(p) as conn:
        ba.init_bridge_schema(conn.cursor())
        conn.commit()
    monkeypatch.setenv("DB_PATH", str(p))
    return str(p)


@pytest.fixture
def app(db_path):
    app = Flask(__name__)
    app.config["TESTING"] = True
    fed.register_federation_routes(app)
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def _seed(db_path, rows):
    """Helper to insert bridge_transfers test rows.

    Each row dict can override any column; sensible defaults applied.
    """
    now = int(time.time())
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        for i, row in enumerate(rows):
            r = {
                "direction": row.get("direction", "deposit"),
                "source_chain": row.get("source_chain", "rustchain"),
                "dest_chain": row.get("dest_chain", "ergo"),
                "source_address": row.get("source_address", f"miner_{i}"),
                "dest_address": row.get("dest_address", f"ergo_addr_{i}"),
                "amount_i64": row.get("amount_i64", 1_000_000),
                "amount_rtc": row.get("amount_rtc", 1.0),
                "bridge_type": row.get("bridge_type", "bottube"),
                "bridge_fee_i64": row.get("bridge_fee_i64", 0),
                "external_tx_hash": row.get("external_tx_hash"),
                "external_confirmations": row.get("external_confirmations", 0),
                "required_confirmations": row.get("required_confirmations", 12),
                "status": row.get("status", "pending"),
                "lock_epoch": row.get("lock_epoch", 1),
                "created_at": row.get("created_at", now - i),
                "updated_at": row.get("updated_at", now - i),
                "tx_hash": row.get("tx_hash", f"hash_{i}"),
            }
            cur.execute(
                """
                INSERT INTO bridge_transfers (
                    direction, source_chain, dest_chain,
                    source_address, dest_address,
                    amount_i64, amount_rtc,
                    bridge_type, bridge_fee_i64,
                    external_tx_hash, external_confirmations, required_confirmations,
                    status, lock_epoch, created_at, updated_at, tx_hash
                ) VALUES (:direction, :source_chain, :dest_chain,
                          :source_address, :dest_address,
                          :amount_i64, :amount_rtc,
                          :bridge_type, :bridge_fee_i64,
                          :external_tx_hash, :external_confirmations, :required_confirmations,
                          :status, :lock_epoch, :created_at, :updated_at, :tx_hash)
                """,
                r,
            )
        conn.commit()


# ---------- /bridge/state ----------------------------------------------------


def test_state_empty(client):
    resp = client.get("/bridge/state")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    s = body["state"]
    assert s["locked_in_rtc"] == 0.0
    assert s["completed_in_rtc"] == 0.0
    assert s["voided_in_rtc"] == 0.0
    assert s["by_status"] == {}
    assert s["by_direction"] == {}
    assert s["last_event_at"] == 0
    assert s["computed_at"] > 0


def test_state_aggregates_by_status_and_direction(client, db_path):
    _seed(db_path, [
        {"status": "pending", "amount_rtc": 10.0, "direction": "deposit"},
        {"status": "locked", "amount_rtc": 20.0, "direction": "deposit"},
        {"status": "confirming", "amount_rtc": 5.0, "direction": "deposit"},
        {"status": "completed", "amount_rtc": 100.0, "direction": "withdraw"},
        {"status": "voided", "amount_rtc": 7.0, "direction": "deposit"},
    ])
    body = client.get("/bridge/state").get_json()
    s = body["state"]
    # locked_in = pending + locked + confirming = 10 + 20 + 5
    assert s["locked_in_rtc"] == 35.0
    assert s["completed_in_rtc"] == 100.0
    assert s["voided_in_rtc"] == 7.0
    assert s["by_status"]["pending"] == {"count": 1, "total_rtc": 10.0}
    assert s["by_status"]["locked"] == {"count": 1, "total_rtc": 20.0}
    assert s["by_direction"]["deposit"]["count"] == 4
    assert s["by_direction"]["deposit"]["total_rtc"] == 42.0  # 10+20+5+7
    assert s["by_direction"]["withdraw"] == {"count": 1, "total_rtc": 100.0}


def test_state_last_event_at_reflects_max_created_at(client, db_path):
    base = int(time.time())
    _seed(db_path, [
        {"created_at": base - 100, "status": "pending"},
        {"created_at": base, "status": "completed"},
        {"created_at": base - 50, "status": "locked"},
    ])
    s = client.get("/bridge/state").get_json()["state"]
    assert s["last_event_at"] == base


# ---------- /bridge/events ---------------------------------------------------


def test_events_empty(client):
    resp = client.get("/bridge/events")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body == {
        "ok": True,
        "count": 0,
        "limit": fed.DEFAULT_EVENTS_LIMIT,
        "window_seconds": fed.DEFAULT_EVENTS_WINDOW_SECONDS,
        "events": [],
    }


def test_events_returns_recent_in_descending_order(client, db_path):
    base = int(time.time())
    _seed(db_path, [
        {"created_at": base - 100, "tx_hash": "old"},
        {"created_at": base - 10, "tx_hash": "newer"},
        {"created_at": base - 50, "tx_hash": "middle"},
    ])
    body = client.get("/bridge/events").get_json()
    assert [e["tx_hash"] for e in body["events"]] == ["newer", "middle", "old"]


def test_events_excludes_sensitive_fields(client, db_path):
    _seed(db_path, [{
        "source_address": "miner_alice",
        "dest_address": "ergo_bob",
        "external_tx_hash": "ergo_external_tx_xxx",
        "tx_hash": "hash_redact_test",
        "status": "completed",
        "amount_rtc": 42.0,
    }])
    e = client.get("/bridge/events").get_json()["events"][0]
    # exposed (safe) fields
    assert "tx_hash" in e
    assert "direction" in e
    assert "amount_rtc" in e
    assert e["status"] == "completed"
    # explicitly NOT exposed
    assert "source_address" not in e
    assert "dest_address" not in e
    assert "external_tx_hash" not in e
    assert "id" not in e
    assert "bridge_fee_i64" not in e
    assert "lock_epoch" not in e


def test_events_window_seconds_clamps_old_rows(client, db_path):
    base = int(time.time())
    _seed(db_path, [
        {"created_at": base - 10_000, "tx_hash": "ten_thousand_ago"},
        {"created_at": base - 10, "tx_hash": "recent"},
    ])
    body = client.get("/bridge/events?window_seconds=100").get_json()
    assert [e["tx_hash"] for e in body["events"]] == ["recent"]


def test_events_limit_clamped_to_max(client, db_path):
    # request limit > MAX_EVENTS_LIMIT should clamp
    _seed(db_path, [{"created_at": int(time.time()) - i} for i in range(5)])
    body = client.get(f"/bridge/events?limit={fed.MAX_EVENTS_LIMIT + 5000}").get_json()
    assert body["limit"] == fed.MAX_EVENTS_LIMIT


def test_events_limit_invalid_falls_back_to_default(client):
    body = client.get("/bridge/events?limit=not_a_number").get_json()
    assert body["limit"] == fed.DEFAULT_EVENTS_LIMIT


# ---------- /bridge/transfers/recent ----------------------------------------


def test_transfers_recent_empty(client):
    body = client.get("/bridge/transfers/recent").get_json()
    assert body == {
        "ok": True,
        "transfers": [],
        "total": 0,
        "limit": fed.DEFAULT_TRANSFERS_LIMIT,
        "offset": 0,
    }


def test_transfers_recent_pagination(client, db_path):
    _seed(db_path, [{"tx_hash": f"h{i}", "created_at": int(time.time()) - i} for i in range(10)])
    body = client.get("/bridge/transfers/recent?limit=3&offset=0").get_json()
    assert body["total"] == 10
    assert body["limit"] == 3
    assert body["offset"] == 0
    assert len(body["transfers"]) == 3
    assert [t["tx_hash"] for t in body["transfers"]] == ["h0", "h1", "h2"]

    body2 = client.get("/bridge/transfers/recent?limit=3&offset=3").get_json()
    assert [t["tx_hash"] for t in body2["transfers"]] == ["h3", "h4", "h5"]


def test_transfers_recent_status_filter(client, db_path):
    _seed(db_path, [
        {"tx_hash": "p1", "status": "pending"},
        {"tx_hash": "c1", "status": "completed"},
        {"tx_hash": "p2", "status": "pending"},
    ])
    body = client.get("/bridge/transfers/recent?status=pending").get_json()
    assert body["total"] == 2
    assert {t["tx_hash"] for t in body["transfers"]} == {"p1", "p2"}


def test_transfers_recent_direction_filter(client, db_path):
    _seed(db_path, [
        {"tx_hash": "d1", "direction": "deposit"},
        {"tx_hash": "w1", "direction": "withdraw"},
    ])
    body = client.get("/bridge/transfers/recent?direction=withdraw").get_json()
    assert body["total"] == 1
    assert body["transfers"][0]["tx_hash"] == "w1"


def test_transfers_recent_invalid_status_ignored(client, db_path):
    _seed(db_path, [{"tx_hash": "x"}])
    body = client.get("/bridge/transfers/recent?status=__not_a_status__").get_json()
    assert body["total"] == 1


def test_transfers_recent_excludes_sensitive_fields(client, db_path):
    _seed(db_path, [{
        "tx_hash": "redact_check",
        "source_address": "secret_src",
        "dest_address": "secret_dst",
        "external_tx_hash": "secret_external",
    }])
    t = client.get("/bridge/transfers/recent").get_json()["transfers"][0]
    assert t["tx_hash"] == "redact_check"
    for field in ("source_address", "dest_address", "external_tx_hash",
                  "id", "bridge_fee_i64", "lock_epoch"):
        assert field not in t


def test_transfers_recent_limit_clamped(client):
    body = client.get(f"/bridge/transfers/recent?limit={fed.MAX_TRANSFERS_LIMIT + 1000}").get_json()
    assert body["limit"] == fed.MAX_TRANSFERS_LIMIT


def test_transfers_recent_offset_negative_clamps_to_zero(client):
    body = client.get("/bridge/transfers/recent?offset=-50").get_json()
    assert body["offset"] == 0


# ---------- routes do not require admin key ---------------------------------


def test_routes_do_not_check_admin_key(client, db_path):
    # No X-Admin-Key header — all 3 routes should still return 200.
    for path in ("/bridge/state", "/bridge/events", "/bridge/transfers/recent"):
        resp = client.get(path)
        assert resp.status_code == 200, f"{path} should not require admin key"


def test_routes_ignore_admin_key_when_present(client, db_path):
    # Routes are explicitly public; supplying a bogus admin key MUST NOT cause
    # a 401 — the routes don't check auth at all.
    headers = {"X-Admin-Key": "bogus"}
    for path in ("/bridge/state", "/bridge/events", "/bridge/transfers/recent"):
        resp = client.get(path, headers=headers)
        assert resp.status_code == 200
