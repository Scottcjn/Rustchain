"""Tests for SophiaCore Attestation Inspector."""
import json
import os
import tempfile
import pytest

# Patch DB path before importing sophia_core modules
import node.sophia_core.db as db_module


class TempDB:
    """Context manager for temporary database."""

    def __init__(self):
        self.path = None

    def __enter__(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        # Patch module-level DB path
        self._orig_path = db_module.DB_PATH
        db_module.DB_PATH = self.path
        # Reload to re-init on temp path
        import importlib
        importlib.reload(db_module)
        return self

    def __exit__(self, *args):
        db_module.DB_PATH = self._orig_path
        import importlib
        importlib.reload(db_module)
        if self.path and os.path.exists(self.path):
            os.unlink(self.path)


# ─── Inspector tests ────────────────────────────────────────────────────────

from node.sophia_core.inspector import evaluate_fingerprint, compute_fingerprint_hash, Verdict


def test_approved_fingerprint():
    fp = {
        "cpu_arch": "x86_64",
        "cpu_model": "Intel Xeon E5-2680",
        "cpu_cores": 16,
        "memory_gb": 64,
        "gpu_model": "NVIDIA GeForce RTX 3090",
        "gpu_count": 2,
        "os": "Linux",
        "has_tpm": True,
        "boot_mode": "UEFI",
        "rng_hardware": True,
        "enclave_support": True,
        "挖矿_duration_days": 90,
    }
    verdict, confidence, reasoning = evaluate_fingerprint(fp)
    assert verdict == Verdict.APPROVED
    assert confidence >= 0.80
    assert "Score=" in reasoning


def test_suspicious_fingerprint():
    fp = {
        "cpu_arch": "unknown_arch",
        "cpu_model": "Fake CPU",
        "cpu_cores": 1,
        "memory_gb": 2,
        "gpu_model": "",
        "gpu_count": 0,
        "os": "Unknown",
        "has_tpm": False,
        "boot_mode": "BIOS",
        "rng_hardware": False,
        "enclave_support": False,
        "挖矿_duration_days": 0,
    }
    verdict, confidence, reasoning = evaluate_fingerprint(fp)
    assert verdict in (Verdict.SUSPICIOUS, Verdict.REJECTED)
    assert confidence < 0.50


def test_test_mode_deterministic():
    fp = {"cpu_arch": "x86_64", "cpu_model": "Test CPU", "cpu_cores": 4, "memory_gb": 8}
    v1 = evaluate_fingerprint(fp, test_mode=True)
    v2 = evaluate_fingerprint(fp, test_mode=True)
    # Same fingerprint → same verdict in test_mode
    assert v1[0] == v2[0]
    assert v1[1] == v2[1]
    assert "test_mode=true" in v1[2]


def test_compute_fingerprint_hash():
    fp = {"cpu_arch": "x86_64", "cpu_cores": 8}
    h1 = compute_fingerprint_hash(fp)
    h2 = compute_fingerprint_hash(fp)
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex


# ─── DB tests ────────────────────────────────────────────────────────────────

from node.sophia_core import db


def test_save_and_get_verdict():
    with TempDB():
        db.save_inspection(
            miner_id="test-miner-001",
            verdict="APPROVED",
            confidence=0.92,
            reasoning="All checks passed.",
            signature="sig123",
            fingerprint_data='{"cpu_arch":"x86_64"}',
            test_mode=False,
        )
        record = db.get_latest_verdict("test-miner-001")
        assert record is not None
        assert record["verdict"] == "APPROVED"
        assert record["confidence"] == 0.92
        assert record["miner_id"] == "test-miner-001"


def test_history():
    with TempDB():
        for i in range(5):
            db.save_inspection(
                miner_id="test-miner-002",
                verdict="APPROVED",
                confidence=0.80 + i * 0.01,
                reasoning=f"Check {i}",
            )
        hist = db.get_history("test-miner-002", limit=3)
        assert len(hist) == 3
        # Most recent first
        assert hist[0]["confidence"] > hist[1]["confidence"]


def test_queue():
    with TempDB():
        db.save_inspection(miner_id="m1", verdict="CAUTIOUS", confidence=0.65, reasoning="")
        db.save_inspection(miner_id="m2", verdict="SUSPICIOUS", confidence=0.45, reasoning="")
        db.save_inspection(miner_id="m3", verdict="APPROVED", confidence=0.90, reasoning="")
        queue = db.get_queue()
        assert len(queue) == 2
        verdicts = {r["miner_id"]: r["verdict"] for r in queue}
        assert verdicts["m1"] == "CAUTIOUS"
        assert verdicts["m2"] == "SUSPICIOUS"


def test_override_valid():
    with TempDB():
        db.save_inspection(
            miner_id="m-ov",
            verdict="SUSPICIOUS",
            confidence=0.40,
            reasoning="Low score",
        )
        success = db.override_verdict(
            "m-ov", "APPROVED", "Manually verified identity", "SOPHIA_ADMIN_KEY"
        )
        assert success is True
        record = db.get_latest_verdict("m-ov")
        assert record["verdict"] == "APPROVED"
        assert "OVERRIDE" in record["reasoning"]


def test_override_invalid_key():
    with TempDB():
        db.save_inspection(miner_id="m-ov2", verdict="REJECTED", confidence=0.10, reasoning="")
        success = db.override_verdict("m-ov2", "APPROVED", "Bad key", "WRONG_KEY")
        assert success is False


def test_all_miner_ids():
    with TempDB():
        db.save_inspection(miner_id="alice", verdict="APPROVED", confidence=0.9, reasoning="")
        db.save_inspection(miner_id="bob", verdict="CAUTIOUS", confidence=0.7, reasoning="")
        ids = db.get_all_miner_ids()
        assert set(ids) == {"alice", "bob"}


# ─── Route tests (mock Flask test client) ────────────────────────────────────

def test_routes_integration():
    """Smoke test that routes can be imported and blueprint registered."""
    from node.sophia_core.routes import sophia_bp
    assert sophia_bp.name == "sophia"
    # Verify expected endpoints exist
    with pytest.importorskip("flask"):
        from flask import Flask
        app = Flask(__name__)
        app.register_blueprint(sophia_bp, url_prefix="/sophia")
        client = app.test_client()

        # Test /inspect
        resp = client.post(
            "/sophia/inspect",
            json={
                "miner_id": "route-test-001",
                "fingerprint": {
                    "cpu_arch": "x86_64",
                    "cpu_model": "Intel Xeon",
                    "cpu_cores": 16,
                    "memory_gb": 64,
                    "gpu_model": "NVIDIA RTX 3090",
                    "gpu_count": 1,
                    "os": "Linux",
                    "has_tpm": True,
                    "boot_mode": "UEFI",
                    "rng_hardware": True,
                    "enclave_support": False,
                    "挖矿_duration_days": 60,
                },
                "test_mode": True,
            },
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "verdict" in data
        assert "confidence" in data
        assert "signature" in data
        assert data["test_mode"] is True

        # Test /status
        resp = client.get("/sophia/status/route-test-001")
        assert resp.status_code == 200
        assert resp.get_json()["miner_id"] == "route-test-001"

        # Test /queue
        resp = client.get("/sophia/queue")
        assert resp.status_code == 200
        assert "count" in resp.get_json()

        # Test /override with bad key
        resp = client.post(
            "/sophia/override",
            json={
                "miner_id": "route-test-001",
                "new_verdict": "APPROVED",
                "reason": "test",
                "admin_key": "WRONG",
            },
        )
        assert resp.status_code == 403

        # Test /override with correct key
        resp = client.post(
            "/sophia/override",
            json={
                "miner_id": "route-test-001",
                "new_verdict": "APPROVED",
                "reason": "Manual review passed",
                "admin_key": "SOPHIA_ADMIN_KEY",
            },
        )
        assert resp.status_code == 200
        assert resp.get_json()["success"] is True

        # Test /batch unauthorized
        resp = client.post("/sophia/batch")
        assert resp.status_code == 403

        # Test /batch authorized
        resp = client.post(
            "/sophia/batch",
            headers={"X-Admin-Key": "SOPHIA_ADMIN_KEY"},
        )
        assert resp.status_code == 200

        # Test /dashboard
        resp = client.get("/sophia/dashboard")
        assert resp.status_code == 200
        assert b"SophiaCore" in resp.data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
