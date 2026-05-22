# SPDX-License-Identifier: MIT

import importlib.util
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LINUX_MINER_PATH = PROJECT_ROOT / "miners" / "linux" / "rustchain_linux_miner.py"
POWER8_MINER_PATH = PROJECT_ROOT / "miners" / "power8" / "rustchain_power8_miner.py"


class FakeResponse:
    status_code = 200

    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


def load_module(name, path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_linux_miner_balance_uses_current_wallet_endpoint(monkeypatch):
    miner_mod = load_module("rustchain_linux_miner_balance_test", LINUX_MINER_PATH)
    monkeypatch.setattr(miner_mod, "FINGERPRINT_AVAILABLE", False)
    monkeypatch.setattr(miner_mod, "get_linux_serial", lambda: "test-serial")

    miner = miner_mod.LocalMiner(wallet="RTC-test-wallet")
    miner.hw_info = {"arch": "x86_64", "hostname": "test-host"}
    calls = []

    def fake_get(path, action, **kwargs):
        calls.append((path, action, kwargs))
        return FakeResponse({"amount_i64": 2_500_000})

    monkeypatch.setattr(miner, "_get", fake_get)

    assert miner.check_balance() == 2.5
    assert calls[0][0] == "/wallet/balance"
    assert calls[0][1] == "checking wallet balance"
    assert calls[0][2]["params"] == {"miner_id": "x86_64-test-host"}


def test_power8_miner_balance_uses_current_wallet_endpoint(monkeypatch):
    miner_mod = load_module("rustchain_power8_miner_balance_test", POWER8_MINER_PATH)
    monkeypatch.setattr(miner_mod, "FINGERPRINT_AVAILABLE", False)

    miner = miner_mod.LocalMiner(wallet="RTC-power8-wallet")
    miner.hw_info = {"hostname": "test-power8"}
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse({"balance_urtc": "3750000"})

    monkeypatch.setattr(miner_mod.requests, "get", fake_get)

    assert miner.check_balance() == 3.75
    assert calls[0][0] == f"{miner.node_url}/wallet/balance"
    assert calls[0][1]["params"] == {"miner_id": "power8-s824-test-power8"}


def test_miner_balance_helpers_reject_malformed_values():
    linux_mod = load_module("rustchain_linux_miner_balance_test", LINUX_MINER_PATH)
    power8_mod = load_module("rustchain_power8_miner_balance_test", POWER8_MINER_PATH)

    for miner_mod in (linux_mod, power8_mod):
        assert miner_mod._wallet_balance_rtc(["not", "an", "object"]) is None
        assert miner_mod._wallet_balance_rtc({"amount_rtc": float("nan")}) is None
        assert miner_mod._wallet_balance_rtc({"amount_rtc": True}) is None
        assert miner_mod._wallet_balance_rtc({"amount_rtc": "4.5", "balance": 99}) == 4.5
        assert miner_mod._wallet_balance_rtc({"amount_i64": 2_000_000, "balance": 99}) == 2.0
        assert miner_mod._wallet_balance_rtc({"rtc_balance": "1.25"}) == 1.25
