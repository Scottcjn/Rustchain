# SPDX-License-Identifier: MIT

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MINER_PATH = ROOT / "miners" / "windows" / "rustchain_windows_miner.py"


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.ok = 200 <= status_code < 400
        self.text = str(payload)

    def json(self):
        return self._payload


def load_miner_module():
    spec = importlib.util.spec_from_file_location(
        "windows_miner_chain_identity", MINER_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_miner(module):
    miner = module.RustChainMiner.__new__(module.RustChainMiner)
    miner.wallet_address = "RTCwallet"
    miner.miner_id = "windows_local"
    miner.node_url = "https://node.example"
    miner.keypair = {"private_key": "private"}
    miner.public_key = "ab" * 32
    miner._pow_proof = None
    miner._last_submitted_slot = None
    miner.last_header_error = ""
    return miner


def test_eligibility_uses_configured_node_and_attested_wallet(monkeypatch):
    module = load_miner_module()
    miner = make_miner(module)
    captured = {}

    def fake_get(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return FakeResponse({
            "eligible": False,
            "reason": "not_your_turn",
            "slot": 42,
        })

    monkeypatch.setattr(module.requests, "get", fake_get)

    result = miner.check_eligibility()

    assert result["slot"] == 42
    assert captured == {
        "url": "https://node.example/lottery/eligibility",
        "params": {"miner_id": "RTCwallet"},
        "timeout": 10,
    }


def test_header_uses_wallet_identity_and_real_signature_shape(monkeypatch):
    module = load_miner_module()
    miner = make_miner(module)
    signed = {}

    def fake_sign(message, private_key):
        signed["message"] = message
        signed["private_key"] = private_key
        return "cd" * 64

    monkeypatch.setattr(module, "CRYPTO_AVAILABLE", True)
    monkeypatch.setattr(module, "sign_payload", fake_sign, raising=False)
    monkeypatch.setattr(module.time, "time", lambda: 1234)

    payload = miner.generate_header(42)

    message = b"slot:42:miner:RTCwallet:ts:1234"
    assert signed == {"message": message, "private_key": "private"}
    assert payload == {
        "miner_id": "RTCwallet",
        "header": {
            "slot": 42,
            "miner": "RTCwallet",
            "timestamp": 1234,
        },
        "message": message.hex(),
        "signature": "cd" * 64,
        "pubkey": "ab" * 32,
    }


def test_submit_uses_configured_node_and_deduplicates_accepted_slot(monkeypatch):
    module = load_miner_module()
    miner = make_miner(module)
    captured = {}
    payload = {
        "miner_id": "RTCwallet",
        "header": {"slot": 42, "miner": "RTCwallet", "timestamp": 1234},
        "message": "00",
        "signature": "cd" * 64,
        "pubkey": "ab" * 32,
    }

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return FakeResponse({"ok": True})

    monkeypatch.setattr(module.requests, "post", fake_post)

    assert miner.submit_header(payload) is True
    assert miner._last_submitted_slot == 42
    assert captured == {
        "url": "https://node.example/headers/ingest_signed",
        "json": payload,
        "timeout": 15,
    }


def test_submit_deduplicates_rejected_slot_and_records_diagnostic(monkeypatch):
    module = load_miner_module()
    miner = make_miner(module)
    payload = {
        "miner_id": "RTCwallet",
        "header": {"slot": 43, "miner": "RTCwallet", "timestamp": 1234},
        "message": "00",
        "signature": "cd" * 64,
        "pubkey": "ab" * 32,
    }

    def fake_post(url, **kwargs):
        return FakeResponse(
            {"ok": False, "error": "no pubkey registered for miner"},
            status_code=403,
        )

    monkeypatch.setattr(module.requests, "post", fake_post)

    assert miner.submit_header(payload) is False
    assert miner._last_submitted_slot == 43
    assert miner.last_header_error == "HTTP 403 error=no pubkey registered for miner"


def test_submit_request_failure_keeps_slot_retryable(monkeypatch):
    module = load_miner_module()
    miner = make_miner(module)
    miner._last_submitted_slot = 41
    payload = {
        "miner_id": "RTCwallet",
        "header": {"slot": 44, "miner": "RTCwallet", "timestamp": 1234},
        "message": "00",
        "signature": "cd" * 64,
        "pubkey": "ab" * 32,
    }

    def fake_post(url, **kwargs):
        raise module.requests.exceptions.Timeout("timed out")

    monkeypatch.setattr(module.requests, "post", fake_post)

    assert miner.submit_header(payload) is False
    assert miner._last_submitted_slot == 41
    assert miner.last_header_error == "header request failed: timed out"


def test_submit_without_slot_does_not_clear_last_submitted_slot(monkeypatch):
    module = load_miner_module()
    miner = make_miner(module)
    miner._last_submitted_slot = 41
    payload = {
        "miner_id": "RTCwallet",
        "header": {"miner": "RTCwallet", "timestamp": 1234},
        "message": "00",
        "signature": "cd" * 64,
        "pubkey": "ab" * 32,
    }

    def fake_post(url, **kwargs):
        return FakeResponse({"ok": False, "error": "missing slot"}, status_code=400)

    monkeypatch.setattr(module.requests, "post", fake_post)

    assert miner.submit_header(payload) is False
    assert miner._last_submitted_slot == 41
    assert miner.last_header_error == "HTTP 400 error=missing slot"
