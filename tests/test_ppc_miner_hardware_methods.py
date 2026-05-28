# SPDX-License-Identifier: MIT

import importlib.util
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MINER_PATH = PROJECT_ROOT / "miners" / "ppc" / "rustchain_powerpc_g4_miner_v2.2.2.py"


class FakeResponse:
    status_code = 200
    text = ""

    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


def load_ppc_miner():
    module_name = "rustchain_ppc_miner_hardware_test"
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(module_name, MINER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_g4_miner_constructs_with_hardware_helpers():
    miner_mod = load_ppc_miner()

    miner = miner_mod.G4Miner(wallet="RTC-ppc-wallet")

    assert callable(miner._detect_hardware)
    assert callable(miner._get_mac_addresses)
    assert callable(miner._collect_entropy)
    assert miner.hw_info["family"] == "PowerPC"
    assert miner.hw_info["arch"] == "G4"
    assert miner.hw_info["macs"]
    assert miner._collect_entropy(cycles=2, inner=5)["sample_count"] == 2


def test_attest_uses_collect_entropy_after_construction(monkeypatch):
    miner_mod = load_ppc_miner()
    miner = miner_mod.G4Miner(wallet="RTC-ppc-wallet")
    monkeypatch.setattr(miner, "_collect_entropy", lambda: {"variance_ns": 1.0})
    responses = [
        FakeResponse({"nonce": "nonce-1"}),
        FakeResponse({"ok": True}),
    ]

    def fake_post(*_args, **_kwargs):
        return responses.pop(0)

    monkeypatch.setattr(miner_mod.requests, "post", fake_post)

    assert miner.attest() is True
    assert miner.attestation_valid_until > 0
    assert responses == []
