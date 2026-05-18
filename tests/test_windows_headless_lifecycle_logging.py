# SPDX-License-Identifier: MIT
import importlib.util
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MINER_PATH = ROOT / "miners" / "windows" / "rustchain_windows_miner.py"


def _load_windows_miner():
    spec = importlib.util.spec_from_file_location("windows_miner_under_test", MINER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_ensure_ready_emits_attest_and_enroll_success_events(monkeypatch):
    module = _load_windows_miner()
    miner = module.RustChainMiner("RTC02811ff5e2bb4bb4b95eee44c5429cd9525496e7")
    events = []

    def fake_attest():
        miner.attestation_valid_until = time.time() + 580
        return True

    def fake_enroll():
        miner.enrolled = True
        miner.last_enroll = time.time()
        return True

    monkeypatch.setattr(miner, "attest", fake_attest)
    monkeypatch.setattr(miner, "enroll", fake_enroll)

    assert miner._ensure_ready(events.append)
    assert [event["type"] for event in events] == ["attest", "enroll"]
    assert events[0]["message"] == "Attestation submitted"
    assert events[0]["miner_id"] == miner.miner_id
    assert events[0]["attestation_ttl_seconds"] > 0
    assert events[1]["message"] == "Epoch enrollment succeeded"
    assert events[1]["miner_id"] == miner.miner_id


def test_ready_status_and_headless_format_include_lifecycle_details():
    module = _load_windows_miner()
    miner = module.RustChainMiner("RTC02811ff5e2bb4bb4b95eee44c5429cd9525496e7")
    miner.enrolled = True
    miner.attestation_valid_until = time.time() + 60
    events = []

    miner._emit_ready_status(events.append)

    assert events[0]["type"] == "status"
    assert events[0]["enrolled"] is True
    assert "Miner ready" in module._format_headless_event(events[0])
    assert "enrolled=yes" in module._format_headless_event(events[0])
    assert module._format_headless_event({
        "type": "attest",
        "message": "Attestation submitted",
        "miner_id": "windows_abc123",
        "attestation_ttl_seconds": 580,
    }) == "[attest] Attestation submitted miner_id=windows_abc123 ttl=580s"
    assert module._format_headless_event({
        "type": "enroll",
        "message": "Epoch enrollment succeeded",
        "miner_id": "windows_abc123",
    }) == "[enroll] Epoch enrollment succeeded miner_id=windows_abc123"
