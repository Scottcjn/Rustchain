import importlib.util
import sys
import types
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]


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


@pytest.mark.parametrize("path", ("/api/v1/challenge", "/api/v1/revoke"))
def test_json_endpoints_reject_non_object_bodies(client, path):
    response = client.post(path, json=["not", "object"])

    assert response.status_code == 400
    assert response.get_json() == {"error": "JSON object required"}


def test_challenge_accepts_valid_json_body(client, api_module):
    response = client.post("/api/v1/challenge", json={"miner_id": "miner-1"})

    assert response.status_code == 200
    assert api_module.poi_system.issued_for == "miner-1"
    assert response.get_json()["challenge_id"] == "challenge-1"


def test_revoke_accepts_valid_json_body(client, api_module):
    response = client.post(
        "/api/v1/revoke",
        json={"miner_id": "miner-1", "reason": "retired"},
    )

    assert response.status_code == 200
    assert api_module.poi_system.revoked == ("miner-1", "retired")
    assert response.get_json() == {"success": True, "message": "Attestation revoked"}
