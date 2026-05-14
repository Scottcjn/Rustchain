import sys
from pathlib import Path

import pytest
from flask import Flask

sys.path.insert(0, str(Path(__file__).parent.parent / "node"))

from gpu_render_endpoints import register_gpu_render_endpoints


@pytest.fixture
def client(tmp_path):
    app = Flask(__name__)
    db_path = tmp_path / "gpu_render.db"
    register_gpu_render_endpoints(app, str(db_path), admin_key="unused")
    app.config["TESTING"] = True
    return app.test_client()


def test_gpu_write_routes_reject_non_object_json(client):
    routes = [
        "/api/gpu/attest",
        "/api/gpu/escrow",
        "/api/gpu/release",
        "/api/gpu/refund",
    ]

    for route in routes:
        response = client.post(route, json=["not", "an", "object"])

        assert response.status_code == 400
        assert response.get_json()["error"] == "invalid_json"


def test_gpu_write_routes_reject_malformed_string_fields(client):
    cases = [
        ("/api/gpu/attest", {"miner_id": {"id": "miner"}}, "miner_id"),
        (
            "/api/gpu/escrow",
            {
                "job_id": {"id": "job-1"},
                "job_type": "render",
                "from_wallet": "payer",
                "to_wallet": "provider",
                "amount_rtc": "1.0",
            },
            "job_id",
        ),
        (
            "/api/gpu/escrow",
            {
                "job_type": "render",
                "from_wallet": "payer",
                "to_wallet": "provider",
                "amount_rtc": "1.0",
                "escrow_secret": {"secret": "abc"},
            },
            "escrow_secret",
        ),
        (
            "/api/gpu/release",
            {"job_id": "job-1", "actor_wallet": ["payer"], "escrow_secret": "secret"},
            "actor_wallet",
        ),
        (
            "/api/gpu/refund",
            {"job_id": "job-1", "actor_wallet": "provider", "escrow_secret": ["secret"]},
            "escrow_secret",
        ),
    ]

    for route, body, field in cases:
        response = client.post(route, json=body)
        payload = response.get_json()

        assert response.status_code == 400
        assert payload["error"] == "invalid_field_type"
        assert payload["field"] == field
        assert payload["expected"] == "string"
