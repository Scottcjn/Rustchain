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
    miner._last_attempted_slot = None
    miner._last_submitted_slot = None
    miner.last_header_error = ""
    miner.shares_submitted = 0
    miner.shares_accepted = 0
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


def test_failed_header_attempt_is_not_retried_for_same_slot(monkeypatch):
    module = load_miner_module()
    miner = make_miner(module)
    miner.mining = True
    events = []
    attempts = []
    sleeps = []

    monkeypatch.setattr(miner, "_ensure_ready", lambda _callback: True)
    monkeypatch.setattr(miner, "_emit_ready_status", lambda _callback: None)
    monkeypatch.setattr(
        miner,
        "check_eligibility",
        lambda: {"eligible": True, "slot": 42},
    )
    monkeypatch.setattr(miner, "generate_header", lambda slot: {"header": {"slot": slot}})

    def reject(_payload):
        attempts.append(42)
        miner.last_header_error = "HTTP 403 error=no pubkey registered for miner"
        return False

    def stop_after_two_loops(_seconds):
        sleeps.append(_seconds)
        if len(sleeps) == 2:
            miner.mining = False

    monkeypatch.setattr(miner, "submit_header", reject)
    monkeypatch.setattr(module.time, "sleep", stop_after_two_loops)

    miner._mine_loop(events.append)

    assert attempts == [42]
    assert sleeps == [10, 10]
    assert events == [{
        "type": "share",
        "submitted": 1,
        "accepted": 0,
        "success": False,
        "slot": 42,
        "error": "HTTP 403 error=no pubkey registered for miner",
    }]


def test_header_generation_failure_does_not_consume_slot(monkeypatch):
    module = load_miner_module()
    miner = make_miner(module)
    miner.mining = True
    generation_attempts = []
    submission_attempts = []
    events = []
    sleeps = []

    monkeypatch.setattr(miner, "_ensure_ready", lambda _callback: True)
    monkeypatch.setattr(miner, "_emit_ready_status", lambda _callback: None)
    monkeypatch.setattr(
        miner,
        "check_eligibility",
        lambda: {"eligible": True, "slot": 42},
    )

    def generate(slot):
        generation_attempts.append(slot)
        if len(generation_attempts) == 1:
            raise RuntimeError("temporary key load failure")
        return {"header": {"slot": slot}}

    def accept(_payload):
        submission_attempts.append(42)
        miner.last_header_error = "stale error"
        return True

    def stop_after_two_loops(_seconds):
        sleeps.append(_seconds)
        if len(sleeps) == 2:
            miner.mining = False

    monkeypatch.setattr(miner, "generate_header", generate)
    monkeypatch.setattr(miner, "submit_header", accept)
    monkeypatch.setattr(module.time, "sleep", stop_after_two_loops)

    miner._mine_loop(events.append)

    assert generation_attempts == [42, 42]
    assert submission_attempts == [42]
    assert sleeps == [30, 10]
    assert events == [
        {"type": "error", "message": "temporary key load failure"},
        {
            "type": "share",
            "submitted": 1,
            "accepted": 1,
            "success": True,
            "slot": 42,
            "error": "",
        },
    ]
