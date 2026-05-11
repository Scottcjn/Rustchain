import base64
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import validate_genesis


def test_is_valid_mac_accepts_known_apple_prefix_case_insensitive():
    assert validate_genesis.is_valid_mac("00:03:93:AA:BB:CC")
    assert validate_genesis.is_valid_mac("00:0A:27:11:22:33")


def test_is_valid_mac_rejects_short_or_unknown_prefixes():
    assert not validate_genesis.is_valid_mac("")
    assert not validate_genesis.is_valid_mac("de:ad:be:ef:00:01")


def test_is_valid_cpu_matches_retro_powerpc_aliases_case_insensitive():
    assert validate_genesis.is_valid_cpu("PowerPC G4 7450")
    assert validate_genesis.is_valid_cpu("ibook g3")
    assert validate_genesis.is_valid_cpu("MPC7400")


def test_is_valid_cpu_rejects_modern_non_powerpc_strings():
    assert not validate_genesis.is_valid_cpu("Intel Core i7")
    assert not validate_genesis.is_valid_cpu("Apple M2 Pro")


def test_recompute_hash_uses_device_timestamp_message_pipe_join():
    device = "PowerMac G4"
    timestamp = "Mon Jan 01 00:00:00 2001"
    message = "genesis"
    expected = base64.b64encode(
        hashlib.sha1(f"{device}|{timestamp}|{message}".encode("utf-8")).digest()
    ).decode("utf-8")

    assert validate_genesis.recompute_hash(device, timestamp, message) == expected


def test_validate_genesis_accepts_matching_fixture(tmp_path, monkeypatch):
    monkeypatch.setattr(validate_genesis.datetime, "datetime", _FixedDateTime)
    payload = {
        "device": "PowerMac G4",
        "timestamp": "Mon Jan 01 00:00:00 2001",
        "message": "hello retro miners",
        "mac_address": "00:03:93:AA:BB:CC",
        "cpu": "PowerPC G4 7450",
    }
    payload["fingerprint"] = validate_genesis.recompute_hash(
        payload["device"], payload["timestamp"], payload["message"]
    )
    path = tmp_path / "genesis.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    assert validate_genesis.validate_genesis(path)


def test_validate_genesis_rejects_tampered_fingerprint(tmp_path, monkeypatch):
    monkeypatch.setattr(validate_genesis.datetime, "datetime", _FixedDateTime)
    payload = {
        "device": "PowerMac G4",
        "timestamp": "Mon Jan 01 00:00:00 2001",
        "message": "hello retro miners",
        "mac_address": "00:03:93:AA:BB:CC",
        "cpu": "PowerPC G4 7450",
        "fingerprint": "tampered",
    }
    path = tmp_path / "genesis.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    assert not validate_genesis.validate_genesis(path)


class _FixedDateTime(validate_genesis.datetime.datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 1, 1)
