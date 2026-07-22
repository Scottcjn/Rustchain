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


def test_ledger_create_rejects_non_object_json(tmp_path, monkeypatch):
    client, db_path = _make_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/ledger",
        headers={"X-Admin-Key": ADMIN_KEY},
        json=["bounty_id", "contributor", "amount_rtc"],
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": "JSON object required"}
    assert _table_exists(db_path)
    with sqlite3.connect(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM payout_ledger").fetchone()[0]
    assert count == 0


def test_ledger_create_rejects_zero_amount(tmp_path, monkeypatch):
    client, db_path = _make_client(tmp_path, monkeypatch)
    payload = _create_payload()
    payload["amount_rtc"] = 0

    response = client.post(
        "/api/ledger",
        headers={"X-Admin-Key": ADMIN_KEY},
        json=payload,
    )

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "amount_rtc must be a positive finite decimal value"
    }
    with sqlite3.connect(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM payout_ledger").fetchone()[0]
    assert count == 0


def test_ledger_status_update_rejects_non_object_json_before_mutation(tmp_path, monkeypatch):
    client, _db_path = _make_client(tmp_path, monkeypatch)
    payout_ledger.init_payout_ledger_tables()
    record_id = payout_ledger.ledger_create("bug-1", "alice", 25)

    response = client.patch(
        f"/api/ledger/{record_id}/status",
        headers={"X-Admin-Key": ADMIN_KEY},
        json=["status"],
    )

    record = payout_ledger.ledger_get(record_id)
    assert response.status_code == 400
    assert response.get_json() == {"error": "JSON object required"}
    assert record["status"] == "queued"
    assert record["tx_hash"] == ""


def test_ledger_status_update_reports_missing_record(tmp_path, monkeypatch):
    client, db_path = _make_client(tmp_path, monkeypatch)
    payout_ledger.init_payout_ledger_tables()

    response = client.patch(
        "/api/ledger/missing-record/status",
        headers={"X-Admin-Key": ADMIN_KEY},
        json={"status": "confirmed", "tx_hash": "tx-missing"},
    )

    assert response.status_code == 404
    assert response.get_json() == {"error": "not found"}
    assert payout_ledger.ledger_get("missing-record") is None
    with sqlite3.connect(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM payout_ledger").fetchone()[0]
    assert count == 0


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


def test_ledger_status_update_rejects_terminal_overwrite(tmp_path, monkeypatch):
    client, _db_path = _make_client(tmp_path, monkeypatch)
    headers = {"X-Admin-Key": ADMIN_KEY}
    payout_ledger.init_payout_ledger_tables()
    record_id = payout_ledger.ledger_create("bug-1", "alice", 25)
    payout_ledger.ledger_update_status(record_id, "confirmed", tx_hash="tx-1")

    same_status = client.patch(
        f"/api/ledger/{record_id}/status",
        headers=headers,
        json={"status": "confirmed"},
    )
    response = client.patch(
        f"/api/ledger/{record_id}/status",
        headers=headers,
        json={"status": "voided", "notes": "late correction"},
    )

    record = payout_ledger.ledger_get(record_id)
    assert same_status.status_code == 200
    assert response.status_code == 409
    assert response.get_json() == {
        "error": "cannot change terminal payout status from confirmed to voided"
    }
    assert record["status"] == "confirmed"
    assert record["tx_hash"] == "tx-1"


def test_status_advance_preserves_tx_hash_and_notes(tmp_path, monkeypatch):
    """A status advance that omits tx_hash/notes must not blank them.

    Regression: the lifecycle create(notes) → pending(tx_hash) → confirmed
    used to overwrite the audit columns with "" whenever a transition did not
    re-supply them, so a confirmed payout lost the on-chain tx_hash proof.
    """
    client, _db_path = _make_client(tmp_path, monkeypatch)
    headers = {"X-Admin-Key": ADMIN_KEY}
    payout_ledger.init_payout_ledger_tables()
    record_id = payout_ledger.ledger_create(
        "bug-1", "alice", 25, notes="approved by maintainer"
    )

    # Operator broadcasts the payout and records the hash (no notes resent).
    pending = client.patch(
        f"/api/ledger/{record_id}/status",
        headers=headers,
        json={"status": "pending", "tx_hash": "0xDEADBEEF"},
    )
    # After confirmations the caller sends only the status.
    confirmed = client.patch(
        f"/api/ledger/{record_id}/status",
        headers=headers,
        json={"status": "confirmed"},
    )

    record = payout_ledger.ledger_get(record_id)
    assert pending.status_code == 200
    assert confirmed.status_code == 200
    assert record["status"] == "confirmed"
    assert record["tx_hash"] == "0xDEADBEEF"   # preserved through confirm
    assert record["notes"] == "approved by maintainer"  # preserved through pending


def test_status_update_can_still_clear_field_with_explicit_empty(tmp_path, monkeypatch):
    """An explicit empty string still overwrites (preserve-on-None only)."""
    client, _db_path = _make_client(tmp_path, monkeypatch)
    headers = {"X-Admin-Key": ADMIN_KEY}
    payout_ledger.init_payout_ledger_tables()
    record_id = payout_ledger.ledger_create("bug-1", "alice", 25, notes="typo note")

    resp = client.patch(
        f"/api/ledger/{record_id}/status",
        headers=headers,
        json={"status": "pending", "notes": ""},
    )
    record = payout_ledger.ledger_get(record_id)
    assert resp.status_code == 200
    assert record["notes"] == ""
