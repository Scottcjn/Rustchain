import sys
from pathlib import Path

import pytest
from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "node"))

import machine_passport_api


class LedgerStub:
    def __init__(self):
        self.attestation_payload = None
        self.benchmark_payload = None

    def get_passport(self, machine_id):
        return True

    def add_attestation(self, **kwargs):
        self.attestation_payload = kwargs
        return True, "attestation added"

    def add_benchmark(self, **kwargs):
        self.benchmark_payload = kwargs
        return True, "benchmark added"


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


@pytest.mark.parametrize(
    "path",
    (
        "/api/machine-passport/machine-1/attestations",
        "/api/machine-passport/machine-1/benchmarks",
    ),
)
def test_event_routes_reject_non_object_json(client, path):
    response = client.post(path, json=["not", "object"])

    assert response.status_code == 400
    assert response.get_json() == {
        "ok": False,
        "error": "invalid_request",
        "message": "JSON object required",
    }


def test_attestation_route_preserves_empty_body_defaults(client, ledger):
    response = client.post("/api/machine-passport/machine-1/attestations")

    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "message": "attestation added"}
    assert ledger.attestation_payload["machine_id"] == "machine-1"
    assert ledger.attestation_payload["epoch"] is None


def test_benchmark_route_preserves_empty_body_defaults(client, ledger):
    response = client.post("/api/machine-passport/machine-1/benchmarks")

    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "message": "benchmark added"}
    assert ledger.benchmark_payload["machine_id"] == "machine-1"
    assert ledger.benchmark_payload["compute_score"] is None


def test_benchmark_route_accepts_object_json(client, ledger):
    response = client.post(
        "/api/machine-passport/machine-1/benchmarks",
        json={"compute_score": 1250.0, "memory_bandwidth": 3200.5},
    )

    assert response.status_code == 200
    assert ledger.benchmark_payload["compute_score"] == 1250.0
    assert ledger.benchmark_payload["memory_bandwidth"] == 3200.5
