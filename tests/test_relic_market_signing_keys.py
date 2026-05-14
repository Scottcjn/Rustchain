# SPDX-License-Identifier: MIT

import importlib.util
from pathlib import Path

import nacl.signing
import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "bounties" / "issue-2312" / "src" / "relic_market_api.py"


def load_relic_market_api():
    spec = importlib.util.spec_from_file_location("relic_market_api_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def clear_relic_key_env(monkeypatch, module):
    monkeypatch.delenv(module.ReceiptSigner.REQUIRE_STABLE_KEYS_ENV, raising=False)
    for machine_id in module.ReceiptSigner.MACHINE_IDS:
        monkeypatch.delenv(module.ReceiptSigner._key_env_name(machine_id), raising=False)


def test_receipt_signer_does_not_generate_deterministic_fallback_keys(monkeypatch):
    module = load_relic_market_api()
    clear_relic_key_env(monkeypatch, module)

    first = module.ReceiptSigner()
    second = module.ReceiptSigner()

    assert first.machine_keys["vm-001"].encode() != second.machine_keys["vm-001"].encode()


def test_receipt_signer_loads_hex_seed_from_environment(monkeypatch):
    module = load_relic_market_api()
    clear_relic_key_env(monkeypatch, module)
    expected_key = nacl.signing.SigningKey.generate()

    monkeypatch.setenv(
        module.ReceiptSigner._key_env_name("vm-001"),
        expected_key.encode().hex(),
    )

    signer = module.ReceiptSigner()

    assert signer.machine_keys["vm-001"].encode() == expected_key.encode()
    assert signer.get_public_key("vm-001") == expected_key.verify_key.encode().hex()


def test_receipt_signer_rejects_invalid_environment_seed(monkeypatch):
    module = load_relic_market_api()
    clear_relic_key_env(monkeypatch, module)
    monkeypatch.setenv(module.ReceiptSigner._key_env_name("vm-001"), "not-a-valid-seed")

    with pytest.raises(ValueError, match="RELIC_MACHINE_KEY_VM_001"):
        module.ReceiptSigner()


def test_receipt_signer_requires_stable_keys_in_production_mode(monkeypatch):
    module = load_relic_market_api()
    clear_relic_key_env(monkeypatch, module)
    monkeypatch.setenv(module.ReceiptSigner.REQUIRE_STABLE_KEYS_ENV, "1")

    with pytest.raises(ValueError, match="RELIC_MACHINE_KEY_VM_001"):
        module.ReceiptSigner()


def test_receipt_signer_stable_keys_verify_across_restart(monkeypatch):
    module = load_relic_market_api()
    clear_relic_key_env(monkeypatch, module)
    monkeypatch.setenv(module.ReceiptSigner.REQUIRE_STABLE_KEYS_ENV, "1")
    for index, machine_id in enumerate(module.ReceiptSigner.MACHINE_IDS, start=1):
        seed = bytes([index]) * 32
        monkeypatch.setenv(module.ReceiptSigner._key_env_name(machine_id), seed.hex())

    first = module.ReceiptSigner()
    receipt_data = {"receipt_id": "receipt-1", "session_id": "session-1"}
    signature = first.sign_receipt(receipt_data, "vm-001")

    second = module.ReceiptSigner()

    assert second.get_public_key("vm-001") == first.get_public_key("vm-001")
    assert second.verify_signature(receipt_data, signature, "vm-001")


def test_public_seed_literals_removed_from_source():
    source = MODULE_PATH.read_text(encoding="utf-8")

    assert "power8-beast-key-seed-001" not in source
    assert "g5-tower-key-seed-002" not in source
    assert "alphaserver-800-key-seed-005" not in source
