from flask import Flask

import payout_ledger


ADMIN_HEADERS = {"X-Admin-Key": "expected-admin-key"}


def make_client(tmp_path, monkeypatch):
    db_path = tmp_path / "payout-ledger.db"
    monkeypatch.setattr(payout_ledger, "DB_PATH", str(db_path))
    app = Flask(__name__)
    payout_ledger.register_ledger_routes(app)
    return app.test_client(), db_path


def test_ledger_routes_fail_closed_before_table_init_when_admin_key_unset(
    tmp_path, monkeypatch
):
    monkeypatch.delenv("RC_ADMIN_KEY", raising=False)
    client, db_path = make_client(tmp_path, monkeypatch)

    routes = [
        ("GET", "/ledger", None),
        ("GET", "/api/ledger", None),
        ("GET", "/api/ledger/record-1", None),
        ("GET", "/api/ledger/summary", None),
        (
            "POST",
            "/api/ledger",
            {"bounty_id": "bounty-1", "contributor": "alice", "amount_rtc": 5},
        ),
        ("PATCH", "/api/ledger/record-1/status", {"status": "confirmed"}),
    ]

    for method, path, payload in routes:
        response = client.open(path, method=method, json=payload)
        assert response.status_code == 503
        assert response.get_json() == {"error": "RC_ADMIN_KEY not configured"}

    assert not db_path.exists()


def test_wrong_admin_key_does_not_create_or_update_payout_records(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("RC_ADMIN_KEY", "expected-admin-key")
    client, db_path = make_client(tmp_path, monkeypatch)

    denied_create = client.post(
        "/api/ledger",
        headers={"X-Admin-Key": "wrong-admin-key"},
        json={"bounty_id": "bounty-1", "contributor": "alice", "amount_rtc": 5},
    )
    assert denied_create.status_code == 401
    assert denied_create.get_json() == {"error": "unauthorized"}
    assert not db_path.exists()

    created = client.post(
        "/api/ledger",
        headers=ADMIN_HEADERS,
        json={"bounty_id": "bounty-1", "contributor": "alice", "amount_rtc": 5},
    )
    assert created.status_code == 201
    record_id = created.get_json()["id"]

    denied_update = client.patch(
        f"/api/ledger/{record_id}/status",
        headers={"X-Admin-Key": "wrong-admin-key"},
        json={"status": "confirmed", "tx_hash": "0xattacker"},
    )
    assert denied_update.status_code == 401
    assert denied_update.get_json() == {"error": "unauthorized"}

    record = client.get(f"/api/ledger/{record_id}", headers=ADMIN_HEADERS).get_json()
    assert record["status"] == "queued"
    assert record["tx_hash"] == ""


def test_valid_admin_key_can_read_create_and_update_payout_record(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("RC_ADMIN_KEY", "expected-admin-key")
    client, _db_path = make_client(tmp_path, monkeypatch)

    created = client.post(
        "/api/ledger",
        headers=ADMIN_HEADERS,
        json={"bounty_id": "bounty-1", "contributor": "alice", "amount_rtc": 5},
    )
    assert created.status_code == 201
    record_id = created.get_json()["id"]

    updated = client.patch(
        f"/api/ledger/{record_id}/status",
        headers=ADMIN_HEADERS,
        json={"status": "confirmed", "tx_hash": "0xpaid"},
    )
    assert updated.status_code == 200

    record = client.get(f"/api/ledger/{record_id}", headers=ADMIN_HEADERS).get_json()
    assert record["status"] == "confirmed"
    assert record["tx_hash"] == "0xpaid"

    summary = client.get("/api/ledger/summary", headers=ADMIN_HEADERS).get_json()
    assert summary["confirmed"]["count"] == 1
    assert summary["confirmed"]["total_rtc"] == 5
