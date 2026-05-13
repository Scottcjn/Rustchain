# SPDX-License-Identifier: MIT
import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "miner_alerts" / "miner_alerts.py"
spec = importlib.util.spec_from_file_location("miner_alerts", MODULE_PATH)
miner_alerts = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(miner_alerts)


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


def test_fetch_miners_accepts_live_paginated_shape(monkeypatch):
    seen = {}

    def fake_get(url, **kwargs):
        seen["url"] = url
        seen["kwargs"] = kwargs
        return FakeResponse({
            "miners": [
                {"miner": "alpha", "last_attest": 123},
                {"miner": "beta", "last_attest": 456},
            ],
            "pagination": {"total": 2, "count": 2},
        })

    monkeypatch.setattr(miner_alerts.requests, "get", fake_get)

    miners = miner_alerts.fetch_miners()

    assert seen["url"].endswith("/api/miners")
    assert seen["kwargs"]["timeout"] == 15
    assert [miner["miner"] for miner in miners] == ["alpha", "beta"]


def test_fetch_miners_still_accepts_legacy_list_shape(monkeypatch):
    monkeypatch.setattr(
        miner_alerts.requests,
        "get",
        lambda *args, **kwargs: FakeResponse([{"miner": "legacy"}]),
    )

    assert miner_alerts.fetch_miners() == [{"miner": "legacy"}]


def test_fetch_balance_uses_live_wallet_balance_route_and_amount_rtc(monkeypatch):
    seen = {}

    def fake_get(url, **kwargs):
        seen["url"] = url
        seen["kwargs"] = kwargs
        return FakeResponse({"amount_i64": 521140570, "amount_rtc": 521.14057, "miner_id": "alpha"})

    monkeypatch.setattr(miner_alerts.requests, "get", fake_get)

    assert miner_alerts.fetch_balance("alpha") == 521.14057
    assert seen["url"].endswith("/wallet/balance")
    assert seen["kwargs"]["params"] == {"miner_id": "alpha"}


def test_fetch_balance_keeps_backward_compatible_balance_fields(monkeypatch):
    monkeypatch.setattr(
        miner_alerts.requests,
        "get",
        lambda *args, **kwargs: FakeResponse({"balance_rtc": "12.5"}),
    )

    assert miner_alerts.fetch_balance("alpha") == 12.5
