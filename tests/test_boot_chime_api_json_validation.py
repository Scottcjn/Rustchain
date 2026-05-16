# SPDX-License-Identifier: MIT
import io
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

    def capture_and_enroll(self, miner_id, audio_file):
        raise AssertionError("invalid uploads should be rejected before enrollment")

    def submit_proof(self, proof, audio_data):
        raise AssertionError("invalid uploads should be rejected before proof submission")


class BootChimeCaptureStub:
    def __init__(self, *args, **kwargs):
        self.calls = []
        self.saved_paths = []

    def capture(self, duration=None, trigger=False):
        self.calls.append((duration, trigger))
        return object()

    def save_audio(self, captured, path):
        self.saved_paths.append(path)
        Path(path).write_bytes(b"RIFF\x00\x00\x00\x00WAVE")


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
        (BootChimeCaptureStub,),
        {},
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


@pytest.mark.parametrize("path", ("/api/v1/submit", "/api/v1/enroll", "/api/v1/analyze"))
def test_audio_upload_endpoints_reject_non_wav_mime_type(client, path):
    data = {"audio": (io.BytesIO(b"not a wav"), "proof.txt", "text/plain")}
    if path == "/api/v1/submit":
        data.update(
            {
                "miner_id": "miner-1",
                "challenge_id": "challenge-1",
                "timestamp": "123",
            }
        )
    elif path == "/api/v1/enroll":
        data["miner_id"] = "miner-1"

    response = client.post(path, data=data, content_type="multipart/form-data")

    assert response.status_code == 400
    assert response.get_json() == {"error": "only WAV files accepted"}


def test_audio_upload_rejects_invalid_wav_magic(client):
    response = client.post(
        "/api/v1/analyze",
        data={"audio": (io.BytesIO(b"RIFFxxxxNOPE"), "proof.wav", "audio/wav")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": "invalid WAV file"}


def test_audio_upload_rejects_files_larger_than_configured_limit(client, api_module):
    api_module.MAX_AUDIO_UPLOAD_BYTES = 8

    response = client.post(
        "/api/v1/analyze",
        data={"audio": (io.BytesIO(b"RIFFxxxxWAVE"), "proof.wav", "audio/wav")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 413
    assert response.get_json() == {"error": "file too large"}


@pytest.mark.parametrize("duration", ("0", "-1", "30.01", "inf", "not-a-number"))
def test_capture_rejects_out_of_range_duration(client, api_module, duration):
    response = client.post(f"/api/v1/capture?duration={duration}")

    assert response.status_code == 400
    assert response.get_json()["error"].startswith("duration must")
    assert api_module.audio_capture.calls == []


def test_capture_accepts_bounded_duration(client, api_module):
    response = client.post("/api/v1/capture?duration=30&trigger=true")

    assert response.status_code == 200
    assert response.mimetype == "audio/wav"
    assert api_module.audio_capture.calls == [(30.0, True)]
    assert api_module.audio_capture.saved_paths
    assert not Path(api_module.audio_capture.saved_paths[-1]).exists()
