# SPDX-License-Identifier: MIT
import sqlite3

from flask import Flask

import payout_ledger


ADMIN_KEY = "ledger-admin-secret"


def _make_client(tmp_path, monkeypatch, admin_key=ADMIN_KEY):
    db_path = tmp_path / "ledger.db"
    monkeypatch.setattr(payout_ledger, "DB_PATH", str(db_path))
    if admin_key is None:
        monkeypatch.delenv("RC_ADMIN_KEY", raising=False)
    else:
        monkeypatch.setenv("RC_ADMIN_KEY", admin_key)

    app = Flask(__name__)
    payout_ledger.register_ledger_routes(app)
    return app.test_client(), db_path


def _table_exists(db_path):
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='payout_ledger'"
        ).fetchone()
    return row is not None


def _create_payload():
    return {
        "bounty_id": "bug-1",
        "contributor": "alice",
        "amount_rtc": 25,
        "wallet_address": "RTC-alice",
        "notes": "queued by admin",
    }


def test_ledger_routes_fail_closed_when_admin_key_unconfigured(tmp_path, monkeypatch):
    client, db_path = _make_client(tmp_path, monkeypatch, admin_key=None)

    response = client.post("/api/ledger", json=_create_payload())

    assert response.status_code == 503
    assert response.get_json()["error"] == "RC_ADMIN_KEY not configured"
    assert not _table_exists(db_path)


def test_ledger_create_requires_admin_key_before_mutation(tmp_path, monkeypatch):
    client, db_path = _make_client(tmp_path, monkeypatch)

    missing = client.post("/api/ledger", json=_create_payload())
    wrong = client.post(
        "/api/ledger",
        headers={"X-Admin-Key": "wrong"},
        json=_create_payload(),
    )

    assert missing.status_code == 401
    assert wrong.status_code == 401
    assert not _table_exists(db_path)


def test_ledger_reads_require_admin_key(tmp_path, monkeypatch):
    client, _db_path = _make_client(tmp_path, monkeypatch)
    payout_ledger.init_payout_ledger_tables()
    record_id = payout_ledger.ledger_create("bug-1", "alice", 25)

    assert client.get("/ledger").status_code == 401
    assert client.get("/api/ledger").status_code == 401
    assert client.get(f"/api/ledger/{record_id}").status_code == 401
    assert client.get("/api/ledger/summary").status_code == 401


def test_ledger_status_update_requires_admin_key_before_mutation(tmp_path, monkeypatch):
    client, _db_path = _make_client(tmp_path, monkeypatch)
    payout_ledger.init_payout_ledger_tables()
    record_id = payout_ledger.ledger_create("bug-1", "alice", 25)

    missing = client.patch(
        f"/api/ledger/{record_id}/status",
        json={"status": "confirmed", "tx_hash": "tx-1"},
    )
    wrong = client.patch(
        f"/api/ledger/{record_id}/status",
        headers={"X-Admin-Key": "wrong"},
        json={"status": "confirmed", "tx_hash": "tx-1"},
    )

    record = payout_ledger.ledger_get(record_id)
    assert missing.status_code == 401
    assert wrong.status_code == 401
    assert record["status"] == "queued"
    assert record["tx_hash"] == ""


def test_admin_key_allows_create_read_summary_and_status_update(tmp_path, monkeypatch):
    client, _db_path = _make_client(tmp_path, monkeypatch)
    headers = {"X-Admin-Key": ADMIN_KEY}

    create = client.post("/api/ledger", headers=headers, json=_create_payload())
    record_id = create.get_json()["id"]
    list_response = client.get("/api/ledger", headers=headers)
    get_response = client.get(f"/api/ledger/{record_id}", headers=headers)
    summary = client.get("/api/ledger/summary", headers=headers)
    page = client.get("/ledger", headers=headers)
    update = client.patch(
        f"/api/ledger/{record_id}/status",
        headers=headers,
        json={"status": "confirmed", "tx_hash": "tx-1"},
    )

    assert create.status_code == 201
    assert list_response.status_code == 200
    assert get_response.status_code == 200
    assert summary.status_code == 200
    assert page.status_code == 200
    assert update.status_code == 200
    assert payout_ledger.ledger_get(record_id)["status"] == "confirmed"
