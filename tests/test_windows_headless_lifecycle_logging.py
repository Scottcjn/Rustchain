# SPDX-License-Identifier: MIT
import importlib.util
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MINER_SCRIPT = ROOT / "miners" / "windows" / "rustchain_windows_miner.py"


def _load_windows_miner():
    spec = importlib.util.spec_from_file_location(
        "rustchain_windows_miner_under_test",
        MINER_SCRIPT,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _miner_without_init(module):
    miner = object.__new__(module.RustChainMiner)
    miner.attestation_valid_until = 0
    miner.last_enroll = 0
    miner.enrolled = False

    def attest():
        miner.attestation_valid_until = time.time() + 580
        return True

    def enroll():
        miner.enrolled = True
        miner.last_enroll = time.time()
        return True

    miner.attest = attest
    miner.enroll = enroll
    return miner


def test_ready_refresh_emits_headless_audit_events():
    module = _load_windows_miner()
    miner = _miner_without_init(module)
    events = []

    assert miner._ensure_ready(events.append) is True

    assert [event["type"] for event in events] == ["attest", "enroll"]
    assert events[0]["message"] == "Attestation successful"
    assert events[0]["valid_until"] > int(time.time())
    assert events[1]["message"] == "Epoch enrollment successful"
    assert events[1]["last_enroll"] <= int(time.time())


def test_ready_state_does_not_emit_duplicate_lifecycle_events():
    module = _load_windows_miner()
    miner = _miner_without_init(module)
    now = time.time()
    miner.attestation_valid_until = now + 580
    miner.last_enroll = now
    miner.enrolled = True

    def fail_if_called():
        raise AssertionError("fresh miner should not refresh lifecycle state")

    miner.attest = fail_if_called
    miner.enroll = fail_if_called
    events = []

    assert miner._ensure_ready(events.append) is True
    assert events == []


def test_headless_runner_prints_lifecycle_messages(monkeypatch, capsys):
    module = _load_windows_miner()

    class FakeWallet:
        def __init__(self):
            self.wallet_data = {"address": "wallet-from-config"}

        def save_wallet(self, wallet_data=None):
            if wallet_data:
                self.wallet_data = wallet_data

    class FakeMiner:
        def __init__(self, wallet_address):
            self.wallet_address = wallet_address
            self.node_url = "http://node-from-init"
            self.miner_id = "windows_test"
            self.stopped = False

        def start_mining(self, callback):
            callback({"type": "attest", "message": "Attestation successful"})
            callback({"type": "enroll", "message": "Epoch enrollment successful"})

        def stop_mining(self):
            self.stopped = True

    def stop_loop(_seconds):
        raise KeyboardInterrupt

    monkeypatch.setattr(module, "RustChainWallet", FakeWallet)
    monkeypatch.setattr(module, "RustChainMiner", FakeMiner)
    monkeypatch.setattr(module.time, "sleep", stop_loop)

    assert module.run_headless("wallet-from-args", "http://node-from-args") == 0

    output = capsys.readouterr()
    assert "[attest] Attestation successful" in output.out
    assert "[enroll] Epoch enrollment successful" in output.out


def test_headless_runner_uses_default_event_label(monkeypatch, capsys):
    module = _load_windows_miner()

    class FakeWallet:
        wallet_data = {"address": "wallet-from-config"}

        def save_wallet(self, wallet_data=None):
            if wallet_data:
                self.wallet_data = wallet_data

    class FakeMiner:
        node_url = "http://node-from-init"
        miner_id = "windows_test"

        def __init__(self, wallet_address):
            self.wallet_address = wallet_address

        def start_mining(self, callback):
            callback({"message": "Lifecycle message without type"})

        def stop_mining(self):
            pass

    def stop_loop(_seconds):
        raise KeyboardInterrupt

    monkeypatch.setattr(module, "RustChainWallet", FakeWallet)
    monkeypatch.setattr(module, "RustChainMiner", FakeMiner)
    monkeypatch.setattr(module.time, "sleep", stop_loop)

    assert module.run_headless("wallet-from-args", "http://node-from-args") == 0

    output = capsys.readouterr()
    assert "[event] Lifecycle message without type" in output.out
