import gc
import sqlite3

import pytest
from flask import Flask

import payout_ledger


@pytest.fixture
def client(tmp_path):
    db_path = tmp_path / "payout-ledger.db"
    original_db_path = payout_ledger.DB_PATH
    payout_ledger.DB_PATH = str(db_path)
    app = Flask(__name__)
    app.config["TESTING"] = True
    payout_ledger.register_ledger_routes(app)

    with app.test_client() as test_client:
        yield test_client

    payout_ledger.DB_PATH = original_db_path
    gc.collect()


def test_create_rejects_non_object_json(client):
    response = client.post(
        "/api/ledger",
        data="42",
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": "JSON object required"}


@pytest.mark.parametrize("amount", ["not-a-number", "nan", "inf", True, False, 0, -1, "-0.0"])
def test_create_rejects_invalid_amounts(client, amount):
    response = client.post(
        "/api/ledger",
        json={
            "bounty_id": "bounty-1",
            "contributor": "alice",
            "amount_rtc": amount,
        },
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": "amount_rtc must be a finite positive number"}


def test_status_update_rejects_non_object_json(client):
    response = client.patch(
        "/api/ledger/example/status",
        data="[]",
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": "JSON object required"}


def test_valid_create_and_status_update_still_work(client):
    created = client.post(
        "/api/ledger",
        json={
            "bounty_id": "bounty-1",
            "contributor": "alice",
            "amount_rtc": "2.5",
            "bounty_title": "Validation fix",
        },
    )
    assert created.status_code == 201
    record_id = created.get_json()["id"]

    updated = client.patch(f"/api/ledger/{record_id}/status", json={"status": "pending"})
    assert updated.status_code == 200
    assert updated.get_json() == {"id": record_id, "status": "pending"}

    with sqlite3.connect(payout_ledger.DB_PATH) as conn:
        amount, status = conn.execute(
            "SELECT amount_rtc, status FROM payout_ledger WHERE id = ?",
            (record_id,),
        ).fetchone()
    assert amount == 2.5
    assert status == "pending"
