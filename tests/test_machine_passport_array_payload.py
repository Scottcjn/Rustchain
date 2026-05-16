"""Regression tests for machine_passport `/repair-log` and `/lineage` routes.

Before this patch, those endpoints called ``request.get_json()`` and then
``data.get(...)`` directly, so an authenticated array payload would crash
the handler with ``AttributeError`` and return HTTP 500. They now share the
``get_optional_json_object()`` validation helper used by ``/attestations``
and ``/benchmarks`` and reject non-object JSON with HTTP 400.

Cited by vuln-audit tick ``vuln-tick-2026-05-14T1500Z`` (Tier 2 — High).
"""

import sys
from pathlib import Path

import pytest
from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "node"))

import machine_passport_api  # noqa: E402


ADMIN_HEADERS = {"X-Admin-Key": "expected-admin-key"}


class LedgerStub:
    def __init__(self):
        self.repair_payload = None
        self.lineage_payload = None
        self.passport_updates = []

    def get_passport(self, machine_id):
        return True

    def add_repair_entry(self, **kwargs):
        self.repair_payload = kwargs
        return True, "repair added"

    def add_lineage_note(self, **kwargs):
        self.lineage_payload = kwargs
        return True, "lineage added"

    def update_passport(self, machine_id, fields):
        self.passport_updates.append((machine_id, fields))
        return True


@pytest.fixture
def ledger(monkeypatch):
    stub = LedgerStub()
    monkeypatch.setattr(machine_passport_api, "_ledger", stub)
    return stub


@pytest.fixture
def client(ledger, monkeypatch):
    monkeypatch.setenv("ADMIN_KEY", "expected-admin-key")
    app = Flask(__name__)
    app.register_blueprint(machine_passport_api.machine_passport_bp)
    return app.test_client()


# --- /repair-log array-payload regressions ------------------------------------

def test_repair_log_rejects_empty_array_payload(client):
    response = client.post(
        "/api/machine-passport/machine-1/repair-log",
        headers=ADMIN_HEADERS,
        json=[],
    )

    assert response.status_code == 400
    assert response.get_json() == {
        "ok": False,
        "error": "invalid_request",
        "message": "JSON object required",
    }


def test_repair_log_rejects_non_object_array_payload(client):
    response = client.post(
        "/api/machine-passport/machine-1/repair-log",
        headers=ADMIN_HEADERS,
        json=["repair_type", "description"],
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid_request"


def test_repair_log_still_requires_fields_for_empty_object(client):
    """Empty body still gets the existing missing_field error (not 500)."""
    response = client.post(
        "/api/machine-passport/machine-1/repair-log",
        headers=ADMIN_HEADERS,
        json={},
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body["error"] == "missing_field"


def test_repair_log_accepts_valid_object_payload(client, ledger):
    response = client.post(
        "/api/machine-passport/machine-1/repair-log",
        headers=ADMIN_HEADERS,
        json={
            "repair_type": "capacitor_replacement",
            "description": "Replaced C12-C15",
        },
    )

    assert response.status_code == 200
    assert ledger.repair_payload["repair_type"] == "capacitor_replacement"
    assert ledger.repair_payload["description"] == "Replaced C12-C15"


# --- /lineage array-payload regressions ---------------------------------------

def test_lineage_rejects_empty_array_payload(client):
    response = client.post(
        "/api/machine-passport/machine-1/lineage",
        headers=ADMIN_HEADERS,
        json=[],
    )

    assert response.status_code == 400
    assert response.get_json() == {
        "ok": False,
        "error": "invalid_request",
        "message": "JSON object required",
    }


def test_lineage_rejects_non_object_array_payload(client):
    response = client.post(
        "/api/machine-passport/machine-1/lineage",
        headers=ADMIN_HEADERS,
        json=["acquisition"],
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid_request"


def test_lineage_still_requires_event_type_for_empty_object(client):
    response = client.post(
        "/api/machine-passport/machine-1/lineage",
        headers=ADMIN_HEADERS,
        json={},
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body["error"] == "missing_field"


def test_lineage_accepts_valid_object_payload(client, ledger):
    response = client.post(
        "/api/machine-passport/machine-1/lineage",
        headers=ADMIN_HEADERS,
        json={"event_type": "acquisition", "to_owner": "miner-42"},
    )

    assert response.status_code == 200
    assert ledger.lineage_payload["event_type"] == "acquisition"
    # to_owner should still propagate to the passport update path
    assert any(
        update[1].get("owner_miner_id") == "miner-42"
        for update in ledger.passport_updates
    )
