# SPDX-License-Identifier: MIT
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MINER_PATH = ROOT / "miners" / "windows" / "rustchain_windows_miner.py"


def _load_windows_miner():
    spec = importlib.util.spec_from_file_location("windows_miner_under_test", MINER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Response:
    def __init__(self, status_code, payload=None, text=None):
        self.status_code = status_code
        self._payload = payload
        self.text = text if text is not None else ""

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


def test_attest_records_submit_rejection_details(monkeypatch):
    module = _load_windows_miner()
    miner = module.RustChainMiner("RTC877021895fd29d034f35c87e1b37af8534703792")
    miner.node_url = "http://node.example"

    def fake_post(url, **kwargs):
        if url.endswith("/attest/challenge"):
            return _Response(200, {"nonce": "nonce-1"})
        if url.endswith("/attest/submit"):
            return _Response(
                409,
                {
                    "ok": False,
                    "code": "DUPLICATE_HARDWARE",
                    "error": "hardware_already_bound",
                    "message": "This hardware is already registered to wallet RTCabc...",
                },
            )
        raise AssertionError(url)

    monkeypatch.setattr(module.requests, "post", fake_post)
    monkeypatch.setattr(miner, "_collect_entropy", lambda: {"variance_ns": 1.0})
    monkeypatch.setattr(miner, "_build_pow_proof", lambda: None)

    assert miner.attest() is False
    assert miner.last_attestation_error == (
        "submit rejected: HTTP 409 code=DUPLICATE_HARDWARE "
        "error=hardware_already_bound message=This hardware is already registered to wallet RTCabc..."
    )


def test_ensure_ready_prints_last_attestation_error():
    module = _load_windows_miner()
    miner = module.RustChainMiner("RTC877021895fd29d034f35c87e1b37af8534703792")
    miner.last_attestation_error = "submit rejected: HTTP 429 code=IP_RATE_LIMIT"
    miner.attest = lambda: False
    events = []

    assert miner._ensure_ready(events.append) is False
    assert events == [
        {
            "type": "error",
            "message": "Attestation failed: submit rejected: HTTP 429 code=IP_RATE_LIMIT",
        }
    ]


def test_headless_wallet_override_does_not_overwrite_saved_wallet(monkeypatch, tmp_path):
    module = _load_windows_miner()
    saved_wallet = {
        "address": "6445fe3349a52537cf50OLDWALLET",
        "balance": 0.0,
        "created": "2026-05-17T00:00:00",
        "transactions": [],
    }
    wallet_file = tmp_path / "wallet.json"
    wallet_file.write_text(json.dumps(saved_wallet), encoding="utf-8")

    monkeypatch.setattr(module, "WALLET_DIR", tmp_path)
    monkeypatch.setattr(module, "WALLET_FILE", wallet_file)
    monkeypatch.setattr(module.time, "sleep", lambda _: (_ for _ in ()).throw(KeyboardInterrupt()))

    started = {}

    def fake_start(self, callback=None):
        started["wallet_address"] = self.wallet_address
        started["saved_wallet"] = module.WALLET_FILE.read_text(encoding="utf-8")

    monkeypatch.setattr(module.RustChainMiner, "start_mining", fake_start)
    monkeypatch.setattr(module.RustChainMiner, "stop_mining", lambda self: None)

    assert module.run_headless("RTC877021895fd29d034f35c87e1b37af8534703792", "http://node") == 0
    assert started["wallet_address"] == "RTC877021895fd29d034f35c87e1b37af8534703792"
    assert json.loads(started["saved_wallet"]) == saved_wallet
    assert json.loads(wallet_file.read_text(encoding="utf-8")) == saved_wallet
