# SPDX-License-Identifier: MIT

from pathlib import Path
import importlib.util


ROOT = Path(__file__).resolve().parents[1]
MINER_PATH = ROOT / "miners" / "macos" / "rustchain_mac_miner_v2.5.py"


class FakeResponse:
    def __init__(self, payload=None, status_code=200):
        self._payload = payload or {}
        self.status_code = status_code
        self.text = str(self._payload)

    def json(self):
        return self._payload


class FakeTransport:
    def __init__(self):
        self.posts = []
        self.gets = []

    def post(self, path, json=None, timeout=None):
        self.posts.append({"path": path, "json": json, "timeout": timeout})
        if path == "/attest/challenge":
            return FakeResponse({"nonce": "nonce-1"})
        return FakeResponse({"ok": True})

    def get(self, path, params=None, timeout=None):
        self.gets.append({"path": path, "params": params, "timeout": timeout})
        return FakeResponse({"eligible": False, "reason": "not_your_turn", "slot": 1})


def load_miner_module():
    spec = importlib.util.spec_from_file_location("mac_miner_v25_identity", MINER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_miner(module):
    miner = module.MacMiner.__new__(module.MacMiner)
    miner.miner_id = "m2-host-hardware"
    miner.wallet = "RTCwallet"
    miner.transport = FakeTransport()
    miner.hw_info = {
        "family": "Apple Silicon",
        "arch": "M2",
        "model": "MacBook Pro",
        "cpu": "Apple M2",
        "cores": 12,
        "memory_gb": 32,
        "serial": "SERIAL",
        "mac": "00:11:22:33:44:55",
        "macs": ["00:11:22:33:44:55"],
        "hostname": "host",
    }
    miner.fingerprint_data = {"all_passed": True, "checks": {}}
    miner.fingerprint_passed = True
    miner.attestation_valid_until = 0
    miner.last_entropy = {}
    miner.shares_submitted = 0
    miner.shares_accepted = 0
    return miner


def test_macos_miner_uses_attested_wallet_for_eligibility(monkeypatch):
    module = load_miner_module()
    monkeypatch.setattr(module, "collect_entropy", lambda: {"variance_ns": 1.0})
    miner = make_miner(module)

    assert miner.attest() is True
    miner.check_eligibility()

    attestation = miner.transport.posts[-1]["json"]
    assert attestation["miner"] == "RTCwallet"
    assert attestation["miner_id"] == "m2-host-hardware"
    assert miner.transport.gets[-1]["params"] == {"miner_id": "RTCwallet"}


def test_macos_miner_submits_headers_with_attested_wallet_identity(monkeypatch):
    module = load_miner_module()
    monkeypatch.setattr(module.time, "time", lambda: 1234)
    miner = make_miner(module)

    ok, result = miner.submit_header(42)

    assert ok is True
    assert result == {"ok": True}
    header = miner.transport.posts[-1]["json"]
    assert header["miner_id"] == "RTCwallet"
    assert header["header"]["miner"] == "RTCwallet"
    assert bytes.fromhex(header["message"]).decode() == "slot:42:miner:RTCwallet:ts:1234"
