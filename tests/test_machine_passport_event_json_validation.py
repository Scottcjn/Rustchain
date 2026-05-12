import sys
from pathlib import Path

import pytest
from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "node"))

import machine_passport_api


class LedgerStub:
    def __init__(self):
        self.repair_payload = None
        self.attestation_payload = None
        self.benchmark_payload = None
        self.lineage_payload = None
        self.update_payload = None

    def get_passport(self, machine_id):
        return True

    def add_repair_entry(self, **kwargs):
        self.repair_payload = kwargs
        return True, "repair added"

    def add_attestation(self, **kwargs):
        self.attestation_payload = kwargs
        return True, "attestation added"

    def add_benchmark(self, **kwargs):
        self.benchmark_payload = kwargs
        return True, "benchmark added"

    def add_lineage_note(self, **kwargs):
        self.lineage_payload = kwargs
        return True, "lineage added"

    def update_passport(self, machine_id, data):
        self.update_payload = {"machine_id": machine_id, "data": data}
        return True, "updated"

    def assert_no_writes(self):
        assert self.repair_payload is None
        assert self.attestation_payload is None
        assert self.benchmark_payload is None
        assert self.lineage_payload is None
        assert self.update_payload is None


@pytest.fixture
def ledger(monkeypatch):
    stub = LedgerStub()
    monkeypatch.setattr(machine_passport_api, "_ledger", stub)
    return stub


@pytest.fixture
def client(ledger):
    app = Flask(__name__)
    app.register_blueprint(machine_passport_api.machine_passport_bp)
    return app.test_client()


@pytest.fixture
def auth_headers(monkeypatch):
    monkeypatch.setenv("ADMIN_KEY", "expected-admin-key")
    return {"X-Admin-Key": "expected-admin-key"}


@pytest.mark.parametrize(
    "path",
    (
        "/api/machine-passport/machine-1/attestations",
        "/api/machine-passport/machine-1/benchmarks",
    ),
)
def test_event_routes_reject_non_object_json(client, path, auth_headers):
    response = client.post(path, json=["not", "object"], headers=auth_headers)

    assert response.status_code == 400
    assert response.get_json() == {
        "ok": False,
        "error": "invalid_request",
        "message": "JSON object required",
    }


@pytest.mark.parametrize(
    "path",
    (
        "/api/machine-passport/machine-1/repair-log",
        "/api/machine-passport/machine-1/attestations",
        "/api/machine-passport/machine-1/benchmarks",
        "/api/machine-passport/machine-1/lineage",
    ),
)
def test_event_write_routes_fail_closed_when_admin_key_unset(
    client,
    ledger,
    monkeypatch,
    path,
):
    monkeypatch.delenv("ADMIN_KEY", raising=False)

    response = client.post(path, json={"event_type": "transfer"})

    assert response.status_code == 503
    assert response.get_json() == {
        "ok": False,
        "error": "admin_key_not_configured",
        "message": "Admin key is not configured",
    }
    ledger.assert_no_writes()


@pytest.mark.parametrize(
    "headers",
    (
        {},
        {"X-Admin-Key": "wrong-admin-key"},
        {"X-API-Key": "wrong-admin-key"},
    ),
)
@pytest.mark.parametrize(
    "path",
    (
        "/api/machine-passport/machine-1/repair-log",
        "/api/machine-passport/machine-1/attestations",
        "/api/machine-passport/machine-1/benchmarks",
        "/api/machine-passport/machine-1/lineage",
    ),
)
def test_event_write_routes_reject_missing_or_wrong_admin_key(
    client,
    ledger,
    monkeypatch,
    path,
    headers,
):
    monkeypatch.setenv("ADMIN_KEY", "expected-admin-key")

    response = client.post(path, json={"event_type": "transfer"}, headers=headers)

    assert response.status_code == 401
    assert response.get_json() == {
        "ok": False,
        "error": "unauthorized",
        "message": "Admin key required",
    }
    ledger.assert_no_writes()


def test_event_write_routes_reject_malformed_admin_key_without_500(
    client,
    ledger,
    monkeypatch,
):
    monkeypatch.setenv("ADMIN_KEY", "expected-admin-key")

    response = client.post(
        "/api/machine-passport/machine-1/repair-log",
        json={"event_type": "transfer"},
        headers={"X-Admin-Key": "é"},
    )

    assert response.status_code == 401
    assert response.get_json() == {
        "ok": False,
        "error": "unauthorized",
        "message": "Admin key required",
    }
    ledger.assert_no_writes()


def test_repair_route_accepts_admin_key_header(client, ledger, auth_headers):
    response = client.post(
        "/api/machine-passport/machine-1/repair-log",
        json={"repair_type": "capacitor_replacement", "description": "recapped board"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "message": "repair added"}
    assert ledger.repair_payload["machine_id"] == "machine-1"
    assert ledger.repair_payload["repair_type"] == "capacitor_replacement"


def test_event_write_routes_accept_legacy_api_key_header(client, ledger, monkeypatch):
    monkeypatch.setenv("ADMIN_KEY", "expected-admin-key")

    response = client.post(
        "/api/machine-passport/machine-1/attestations",
        headers={"X-API-Key": "expected-admin-key"},
    )

    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "message": "attestation added"}
    assert ledger.attestation_payload["machine_id"] == "machine-1"


def test_attestation_route_preserves_empty_body_defaults(client, ledger, auth_headers):
    response = client.post(
        "/api/machine-passport/machine-1/attestations",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "message": "attestation added"}
    assert ledger.attestation_payload["machine_id"] == "machine-1"
    assert ledger.attestation_payload["epoch"] is None


def test_benchmark_route_preserves_empty_body_defaults(client, ledger, auth_headers):
    response = client.post(
        "/api/machine-passport/machine-1/benchmarks",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "message": "benchmark added"}
    assert ledger.benchmark_payload["machine_id"] == "machine-1"
    assert ledger.benchmark_payload["compute_score"] is None


def test_benchmark_route_accepts_object_json(client, ledger, auth_headers):
    response = client.post(
        "/api/machine-passport/machine-1/benchmarks",
        json={"compute_score": 1250.0, "memory_bandwidth": 3200.5},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert ledger.benchmark_payload["compute_score"] == 1250.0
    assert ledger.benchmark_payload["memory_bandwidth"] == 3200.5


def test_lineage_route_updates_owner_with_admin_key(client, ledger, auth_headers):
    response = client.post(
        "/api/machine-passport/machine-1/lineage",
        json={"event_type": "transfer", "to_owner": "new-owner"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "message": "lineage added"}
    assert ledger.lineage_payload["machine_id"] == "machine-1"
    assert ledger.lineage_payload["event_type"] == "transfer"
    assert ledger.update_payload == {
        "machine_id": "machine-1",
        "data": {"owner_miner_id": "new-owner"},
    }
