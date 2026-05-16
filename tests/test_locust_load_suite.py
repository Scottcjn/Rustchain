# SPDX-License-Identifier: MIT
"""Unit tests for the RustChain Locust load-test suite."""

import importlib.util
import json
import sys
import types
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "tools" / "load-tests" / "locustfile.py"


class DummyEvents:
    def __init__(self):
        self.registered = []
        self.quitting = types.SimpleNamespace(add_listener=self.add_listener)

    def add_listener(self, func):
        self.registered.append(func)
        return func


def load_module(monkeypatch, miner_id=None):
    events = DummyEvents()
    locust = types.ModuleType("locust")
    locust.HttpUser = object
    locust.between = lambda low, high: (low, high)
    locust.task = lambda _weight: (lambda func: func)
    locust.events = events
    monkeypatch.setitem(sys.modules, "locust", locust)
    if miner_id is not None:
        monkeypatch.setenv("RUSTCHAIN_MINER_ID", miner_id)
    else:
        monkeypatch.delenv("RUSTCHAIN_MINER_ID", raising=False)

    spec = importlib.util.spec_from_file_location("rustchain_locustfile", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module._registered_events = events.registered
    return module


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self.payload = payload if payload is not None else {}
        self.failures = []

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def json(self):
        return self.payload

    def failure(self, message):
        self.failures.append(message)


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, path, **kwargs):
        self.calls.append((path, kwargs))
        return self.responses.pop(0)


def user_with_client(module, client):
    user = object.__new__(module.RustChainUser)
    user.client = client
    return user


def test_health_and_epoch_tasks_validate_success_payloads(monkeypatch):
    module = load_module(monkeypatch)
    health = FakeResponse(payload={"ok": True})
    epoch = FakeResponse(payload={"epoch": 9})
    client = FakeClient([health, epoch])
    user = user_with_client(module, client)

    user.health()
    user.epoch()

    assert client.calls == [
        ("/health", {"verify": False, "catch_response": True}),
        ("/epoch", {"verify": False, "catch_response": True}),
    ]
    assert health.failures == []
    assert epoch.failures == []


def test_tasks_mark_bad_status_and_missing_keys_as_failures(monkeypatch):
    module = load_module(monkeypatch)
    health = FakeResponse(payload={"ok": False})
    epoch = FakeResponse(payload={})
    headers = FakeResponse(status_code=503)
    miners = FakeResponse(status_code=500)
    balance = FakeResponse(payload={})
    client = FakeClient([health, epoch, headers, miners, balance])
    user = user_with_client(module, client)

    user.health()
    user.epoch()
    user.headers_tip()
    user.api_miners()
    user.wallet_balance()

    assert health.failures == ["health.ok is not True"]
    assert epoch.failures == ["missing 'epoch' key"]
    assert headers.failures == ["status 503"]
    assert miners.failures == ["status 500"]
    assert balance.failures == ["missing 'amount_rtc' key"]


def test_wallet_balance_uses_configured_miner_id(monkeypatch):
    module = load_module(monkeypatch, miner_id="Ada-Miner")
    response = FakeResponse(payload={"amount_rtc": 12.5})
    client = FakeClient([response])
    user = user_with_client(module, client)

    user.wallet_balance()

    assert client.calls[0][0] == "/wallet/balance?miner_id=Ada-Miner"
    assert response.failures == []


def test_quit_hook_writes_summary_json(tmp_path, monkeypatch):
    module = load_module(monkeypatch)
    monkeypatch.chdir(tmp_path)

    class TotalStats:
        num_requests = 42
        num_failures = 2
        avg_response_time = 12.345
        median_response_time = 10
        current_rps = 3.456

        def get_response_time_percentile(self, percentile):
            return {0.95: 50, 0.99: 75}[percentile]

    environment = types.SimpleNamespace(
        runner=types.SimpleNamespace(stats=types.SimpleNamespace(total=TotalStats()))
    )

    module._on_quit(environment)

    summary = json.loads((tmp_path / "results" / "locust_summary.json").read_text())
    assert summary == {
        "total_requests": 42,
        "total_failures": 2,
        "avg_response_time_ms": 12.35,
        "median_ms": 10,
        "p95_ms": 50,
        "p99_ms": 75,
        "requests_per_sec": 3.46,
    }
    assert module._registered_events == [module._on_quit]
