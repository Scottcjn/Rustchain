# SPDX-License-Identifier: MIT
"""Tests for GPU attestation admin-key authentication (issue #6560)."""

import sqlite3
import pytest
from flask import Flask

from node.gpu_render_protocol import GPURenderProtocol, register_routes


ADMIN_KEY = "test-admin-key-6560"


def _create_app(admin_key=ADMIN_KEY):
    app = Flask(__name__)
    app.config["TESTING"] = True
    register_routes(app, admin_key=admin_key)
    return app


@pytest.fixture
def client(tmp_path):
    db_path = tmp_path / "gpu_test.db"
    app = _create_app(admin_key=ADMIN_KEY)
    with app.test_client() as c:
        yield c


@pytest.fixture
def no_key_client():
    """App registered with no admin key."""
    app = _create_app(admin_key="")
    with app.test_client() as c:
        yield c


class TestAttestRequiresAdminKey:
    """POST /gpu/attest must reject unauthenticated requests."""

    def test_attest_no_key_returns_401(self, client):
        """Request without X-Admin-Key header returns 401."""
        resp = client.post("/gpu/attest", json={
            "miner_id": "impersonator",
            "gpu_model": "RTX 4090",
            "vram_gb": 24,
            "device_arch": "nvidia_gpu",
        })
        assert resp.status_code == 401
        data = resp.get_json()
        assert "admin key required" in data["error"].lower() or "unauthorized" in data["error"].lower()

    def test_attest_wrong_key_returns_401(self, client):
        """Request with incorrect key returns 401."""
        resp = client.post("/gpu/attest", json={
            "miner_id": "impersonator",
            "gpu_model": "RTX 4090",
            "vram_gb": 24,
            "device_arch": "nvidia_gpu",
        }, headers={"X-Admin-Key": "wrong-key"})
        assert resp.status_code == 401

    def test_attest_correct_key_succeeds(self, client):
        """Request with correct key returns 200."""
        resp = client.post("/gpu/attest", json={
            "miner_id": "legitimate-miner",
            "gpu_model": "RTX 4090",
            "vram_gb": 24,
            "device_arch": "nvidia_gpu",
        }, headers={"X-Admin-Key": ADMIN_KEY})
        assert resp.status_code == 200
        data = resp.get_json()
        assert "error" not in data

    def test_attest_x_api_key_header_accepted(self, client):
        """X-API-Key header is also accepted (consistent with other admin endpoints)."""
        resp = client.post("/gpu/attest", json={
            "miner_id": "legitimate-miner-2",
            "gpu_model": "RX 7900 XTX",
            "vram_gb": 24,
            "device_arch": "amd_gpu",
        }, headers={"X-API-Key": ADMIN_KEY})
        assert resp.status_code == 200
        data = resp.get_json()
        assert "error" not in data

    def test_attest_no_admin_configured_returns_503(self, no_key_client):
        """If no admin key is configured, attest endpoint is disabled (503)."""
        resp = no_key_client.post("/gpu/attest", json={
            "miner_id": "anyone",
            "gpu_model": "RTX 4090",
            "vram_gb": 24,
            "device_arch": "nvidia_gpu",
        }, headers={"X-Admin-Key": "anything"})
        assert resp.status_code == 503

    def test_read_endpoints_still_public(self, client):
        """GET /gpu/nodes remains publicly accessible."""
        resp = client.get("/gpu/nodes")
        assert resp.status_code == 200


class TestAttestCannotImpersonate:
    """After the fix, unauthenticated callers cannot insert attestations."""

    def test_unauthenticated_attest_does_not_create_record(self, client):
        """A failed auth attempt should not write to the database."""
        # First, add a legitimate attestation
        client.post("/gpu/attest", json={
            "miner_id": "real-miner",
            "gpu_model": "RTX 4090",
            "vram_gb": 24,
            "device_arch": "nvidia_gpu",
            "benchmark_score": 95.0,
        }, headers={"X-Admin-Key": ADMIN_KEY})

        # Try to overwrite without auth
        resp = client.post("/gpu/attest", json={
            "miner_id": "real-miner",
            "gpu_model": "FAKE GPU",
            "vram_gb": 1,
            "device_arch": "nvidia_gpu",
        })
        assert resp.status_code == 401

        # Verify original attestation is unchanged
        nodes_resp = client.get("/gpu/nodes")
        nodes = nodes_resp.get_json()["nodes"]
        real = [n for n in nodes if n.get("miner_id") == "real-miner"]
        assert len(real) == 1
        assert real[0]["gpu_model"] == "RTX 4090"
