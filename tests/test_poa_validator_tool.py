# SPDX-License-Identifier: MIT
"""Unit tests for the legacy genesis validator helper."""

import importlib.util
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "tools" / "validate_genesis.py"


def load_module():
    spec = importlib.util.spec_from_file_location("validate_genesis_tool", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_mac_validation_accepts_known_apple_prefix_case_insensitively():
    module = load_module()

    assert module.is_valid_mac("00:0A:27:12:34:56") is True
    assert module.is_valid_mac("00:16:cb:12:34:56") is False


def test_cpu_validation_accepts_powerpc_generation_markers():
    module = load_module()

    assert module.is_valid_cpu("PowerPC G4 7450") is True
    assert module.is_valid_cpu("Intel Core i7") is False


def test_timestamp_validation_rejects_future_and_pre_macintosh_dates():
    module = load_module()

    assert module.is_reasonable_timestamp("Mon Jan 01 00:00:00 2001") is True
    assert module.is_reasonable_timestamp("Sat Jan 01 00:00:00 2099") is False
    assert module.is_reasonable_timestamp("Sat Jan 01 00:00:00 1983") is False


def test_recompute_hash_is_stable_for_same_genesis_fields():
    module = load_module()

    digest = module.recompute_hash("PowerMac G4", "Mon Jan 01 00:00:00 2001", "hello")

    assert digest == module.recompute_hash("PowerMac G4", "Mon Jan 01 00:00:00 2001", "hello")
    assert digest != module.recompute_hash("PowerMac G4", "Mon Jan 01 00:00:00 2001", "changed")


def test_validate_genesis_accepts_matching_legacy_machine_file(tmp_path):
    module = load_module()
    payload = {
        "device": "PowerMac G4",
        "timestamp": "Mon Jan 01 00:00:00 2001",
        "message": "retro proof",
        "mac_address": "00:03:93:12:34:56",
        "cpu": "PowerPC G4 7400",
    }
    payload["fingerprint"] = module.recompute_hash(
        payload["device"], payload["timestamp"], payload["message"]
    )
    genesis_path = tmp_path / "genesis.json"
    genesis_path.write_text(json.dumps(payload), encoding="utf-8")

    assert module.validate_genesis(genesis_path) is True


def test_validate_genesis_rejects_mismatched_fingerprint(tmp_path):
    module = load_module()
    genesis_path = tmp_path / "genesis.json"
    genesis_path.write_text(
        json.dumps({
            "device": "PowerMac G4",
            "timestamp": "Mon Jan 01 00:00:00 2001",
            "message": "retro proof",
            "mac_address": "00:03:93:12:34:56",
            "cpu": "PowerPC G4 7400",
            "fingerprint": "wrong",
        }),
        encoding="utf-8",
    )

    assert module.validate_genesis(genesis_path) is False
