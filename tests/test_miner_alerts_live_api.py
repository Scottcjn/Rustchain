# SPDX-License-Identifier: MIT

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest


@pytest.fixture()
def miner_alerts_module(monkeypatch):
    fake_dotenv = types.SimpleNamespace(load_dotenv=lambda: None)
    monkeypatch.setitem(sys.modules, "dotenv", fake_dotenv)

    module_path = (
        Path(__file__).resolve().parents[1]
        / "tools"
        / "miner_alerts"
        / "miner_alerts.py"
    )
    spec = importlib.util.spec_from_file_location("miner_alerts_live_api", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    def __init__(self, payload, status_code=200, error=None):
        self.payload = payload
        self.status_code = status_code
        self.error = error

    def raise_for_status(self):
        if self.error:
            raise self.error

    def json(self):
        return self.payload


def test_fetch_miners_accepts_live_paginated_shape(miner_alerts_module, monkeypatch):
    monkeypatch.setattr(miner_alerts_module, "RUSTCHAIN_API", "https://node.example")
    monkeypatch.setattr(miner_alerts_module, "VERIFY_SSL", True)

    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse(
            {
                "miners": [{"miner": "miner-a"}, {"miner_id": "miner-b"}],
                "pagination": {"total": 2},
            }
        )

    monkeypatch.setattr(miner_alerts_module.requests, "get", fake_get)

    assert miner_alerts_module.fetch_miners() == [
        {"miner": "miner-a"},
        {"miner_id": "miner-b"},
    ]
    assert calls == [
        ("https://node.example/api/miners", {"verify": True, "timeout": 15})
    ]


def test_fetch_miners_keeps_legacy_list_support(miner_alerts_module, monkeypatch):
    monkeypatch.setattr(
        miner_alerts_module.requests,
        "get",
        lambda *_args, **_kwargs: FakeResponse([{"miner": "legacy"}]),
    )

    assert miner_alerts_module.fetch_miners() == [{"miner": "legacy"}]


def test_fetch_balance_uses_wallet_balance_endpoint(miner_alerts_module, monkeypatch):
    monkeypatch.setattr(miner_alerts_module, "RUSTCHAIN_API", "https://node.example")
    monkeypatch.setattr(miner_alerts_module, "VERIFY_SSL", False)

    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse({"amount_rtc": "3.5"})

    monkeypatch.setattr(miner_alerts_module.requests, "get", fake_get)

    assert miner_alerts_module.fetch_balance("miner-a") == 3.5
    assert calls == [
        (
            "https://node.example/wallet/balance",
            {"params": {"miner_id": "miner-a"}, "verify": False, "timeout": 10},
        )
    ]


def test_fetch_balance_falls_back_to_path_route(miner_alerts_module, monkeypatch):
    monkeypatch.setattr(miner_alerts_module, "RUSTCHAIN_API", "https://node.example")

    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        if url.endswith("/wallet/balance"):
            return FakeResponse({}, status_code=404)
        return FakeResponse({"balance_rtc": "7.25"})

    monkeypatch.setattr(miner_alerts_module.requests, "get", fake_get)

    assert miner_alerts_module.fetch_balance("miner-a") == 7.25
    assert [url for url, _kwargs in calls] == [
        "https://node.example/wallet/balance",
        "https://node.example/balance/miner-a",
    ]
