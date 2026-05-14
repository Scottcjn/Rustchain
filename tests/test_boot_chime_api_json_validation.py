import importlib.util
import sys
import types
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
ADMIN_KEY = "test-admin-key"


class ChallengeStub:
    challenge_id = "challenge-1"
    nonce = "nonce-1"
    issued_at = 100
    expires_at = 400


class ProofOfIronStub:
    def __init__(self, *args, **kwargs):
        self.issued_for = None
        self.revoked = None

    def issue_challenge(self, miner_id):
        self.issued_for = miner_id
        return ChallengeStub()

    def revoke_attestation(self, miner_id, reason):
        self.revoked = (miner_id, reason)
        return True


def install_dependency_stubs(monkeypatch):
    flask_cors = types.ModuleType("flask_cors")
    flask_cors.CORS = lambda app: app
    monkeypatch.setitem(sys.modules, "flask_cors", flask_cors)

    acoustic_fingerprint = types.ModuleType("acoustic_fingerprint")
    acoustic_fingerprint.AcousticFingerprint = type("AcousticFingerprint", (), {})
    monkeypatch.setitem(sys.modules, "acoustic_fingerprint", acoustic_fingerprint)

    boot_chime_capture = types.ModuleType("boot_chime_capture")
    boot_chime_capture.AudioCaptureConfig = type(
        "AudioCaptureConfig",
        (),
        {"__init__": lambda self, **kwargs: None},
    )
    boot_chime_capture.BootChimeCapture = type(
        "BootChimeCapture",
        (),
        {"__init__": lambda self, *args, **kwargs: None},
    )
    monkeypatch.setitem(sys.modules, "boot_chime_capture", boot_chime_capture)

    proof_of_iron = types.ModuleType("proof_of_iron")
    proof_of_iron.ProofOfIron = ProofOfIronStub
    proof_of_iron.ProofOfIronError = Exception
    proof_of_iron.AttestationStatus = type(
        "AttestationStatus",
        (),
        {"VERIFIED": "verified"},
    )
    monkeypatch.setitem(sys.modules, "proof_of_iron", proof_of_iron)


@pytest.fixture
def api_module(monkeypatch):
    monkeypatch.setenv("BOOT_CHIME_ADMIN_KEY", ADMIN_KEY)
    monkeypatch.delenv("RC_ADMIN_KEY", raising=False)
    install_dependency_stubs(monkeypatch)
    module_path = REPO_ROOT / "issue2307_boot_chime" / "boot_chime_api.py"
    spec = importlib.util.spec_from_file_location("boot_chime_api_under_test", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def client(api_module):
    api_module.app.config["TESTING"] = True
    return api_module.app.test_client()


def admin_headers():
    return {"X-Admin-Key": ADMIN_KEY}


@pytest.mark.parametrize(
    "path, kwargs",
    (
        ("/api/v1/challenge", {"json": {"miner_id": "miner-1"}}),
        ("/api/v1/submit", {"data": {"miner_id": "miner-1", "challenge_id": "c1", "timestamp": "100"}}),
        ("/api/v1/enroll", {"data": {"miner_id": "miner-1"}}),
        ("/api/v1/capture", {}),
        ("/api/v1/revoke", {"json": {"miner_id": "miner-1"}}),
    ),
)
def test_mutating_endpoints_require_admin_key(client, path, kwargs):
    response = client.post(path, **kwargs)

    assert response.status_code == 401
    assert response.get_json() == {"error": "unauthorized"}


def test_mutating_endpoints_fail_closed_without_configured_admin_key(client, monkeypatch):
    monkeypatch.delenv("BOOT_CHIME_ADMIN_KEY", raising=False)
    monkeypatch.delenv("RC_ADMIN_KEY", raising=False)

    response = client.post(
        "/api/v1/revoke",
        headers=admin_headers(),
        json={"miner_id": "miner-1"},
    )

    assert response.status_code == 503
    assert response.get_json() == {"error": "BOOT_CHIME_ADMIN_KEY or RC_ADMIN_KEY not configured"}


def test_authorization_bearer_admin_key_is_accepted(client, api_module):
    response = client.post(
        "/api/v1/challenge",
        headers={"Authorization": f"Bearer {ADMIN_KEY}"},
        json={"miner_id": "miner-1"},
    )

    assert response.status_code == 200
    assert api_module.poi_system.issued_for == "miner-1"


@pytest.mark.parametrize("path", ("/api/v1/challenge", "/api/v1/revoke"))
def test_json_endpoints_reject_non_object_bodies(client, path):
    response = client.post(path, headers=admin_headers(), json=["not", "object"])

    assert response.status_code == 400
    assert response.get_json() == {"error": "JSON object required"}


def test_challenge_accepts_valid_json_body(client, api_module):
    response = client.post(
        "/api/v1/challenge",
        headers=admin_headers(),
        json={"miner_id": "miner-1"},
    )

    assert response.status_code == 200
    assert api_module.poi_system.issued_for == "miner-1"
    assert response.get_json()["challenge_id"] == "challenge-1"


def test_revoke_accepts_valid_json_body(client, api_module):
    response = client.post(
        "/api/v1/revoke",
        headers=admin_headers(),
        json={"miner_id": "miner-1", "reason": "retired"},
    )

    assert response.status_code == 200
    assert api_module.poi_system.revoked == ("miner-1", "retired")
    assert response.get_json() == {"success": True, "message": "Attestation revoked"}
