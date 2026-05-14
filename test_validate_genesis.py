# SPDX-License-Identifier: MIT

import importlib.util
import json
from datetime import datetime, timedelta
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parent / "tools" / "validate_genesis.py"
SPEC = importlib.util.spec_from_file_location("validate_genesis", MODULE_PATH)
validate_genesis = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validate_genesis)


def test_validators_accept_known_vintage_apple_inputs():
    assert validate_genesis.is_valid_mac("00:03:93:aa:bb:cc") is True
    assert validate_genesis.is_valid_mac("00:0A:27:aa:bb:cc") is True
    assert validate_genesis.is_valid_cpu("PowerPC G4 7450") is True
    assert validate_genesis.is_reasonable_timestamp("Tue Jan 24 03:00:00 1984") is True


def test_validators_reject_unknown_or_future_inputs():
    future = (datetime.now() + timedelta(days=1)).strftime("%a %b %d %H:%M:%S %Y")

    assert validate_genesis.is_valid_mac("de:ad:be:ef:00:01") is False
    assert validate_genesis.is_valid_cpu("Intel Core i9") is False
    assert validate_genesis.is_reasonable_timestamp(future) is False
    assert validate_genesis.is_reasonable_timestamp("not a timestamp") is False


def test_recompute_hash_is_stable_for_genesis_fields():
    assert validate_genesis.recompute_hash(
        "PowerMac G4",
        "Tue Jan 24 03:00:00 1984",
        "first retro miner",
    ) == "ETwD86kr4qTaD8ixZEoKzqMCG+8="


def test_validate_genesis_accepts_matching_fixture(tmp_path, capsys):
    timestamp = "Tue Jan 24 03:00:00 1984"
    payload = {
        "device": "PowerMac G4",
        "timestamp": timestamp,
        "message": "first retro miner",
        "fingerprint": validate_genesis.recompute_hash(
            "PowerMac G4",
            timestamp,
            "first retro miner",
        ),
        "mac_address": "00:03:93:aa:bb:cc",
        "cpu": "PowerPC G4 7450",
    }
    path = tmp_path / "genesis.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    assert validate_genesis.validate_genesis(path) is True
    assert "Genesis is verified and authentic" in capsys.readouterr().out


def test_validate_genesis_reports_invalid_fixture(tmp_path, capsys):
    payload = {
        "device": "Modern PC",
        "timestamp": "not a timestamp",
        "message": "changed",
        "fingerprint": "wrong",
        "mac_address": "de:ad:be:ef:00:01",
        "cpu": "Intel Core i9",
    }
    path = tmp_path / "genesis.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    assert validate_genesis.validate_genesis(path) is False
    output = capsys.readouterr().out
    assert "Validation Failed" in output
    assert "MAC address not in known Apple ranges" in output
    assert "CPU string not recognized as retro PowerPC" in output
    assert "Timestamp is invalid or too modern" in output
    assert "Fingerprint hash does not match contents" in output
