#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

import socket

from webhook_server import (
    RustChainPoller,
    SubscriberStore,
    WebhookEvent,
    dispatch_event,
    validate_webhook_url,
)


def _addrinfo(*ips):
    return [
        (
            socket.AF_INET6 if ":" in ip else socket.AF_INET,
            socket.SOCK_STREAM,
            6,
            "",
            (ip, 443),
        )
        for ip in ips
    ]


def test_validate_webhook_url_rejects_invalid_shape_without_dns(monkeypatch):
    def fail_getaddrinfo(*args, **kwargs):
        raise AssertionError("DNS lookup should not run for invalid URL shape")

    monkeypatch.setattr(socket, "getaddrinfo", fail_getaddrinfo)

    assert validate_webhook_url("ftp://example.com/hook") == (
        "url must use http or https scheme"
    )
    assert validate_webhook_url("https:///missing-host") == (
        "url must contain a hostname"
    )


def test_validate_webhook_url_rejects_dns_failures(monkeypatch):
    def raise_gaierror(hostname, port):
        raise socket.gaierror("not found")

    monkeypatch.setattr(socket, "getaddrinfo", raise_gaierror)

    assert validate_webhook_url("https://missing.example/hook") == (
        "url hostname could not be resolved"
    )


def test_validate_webhook_url_rejects_any_blocked_resolved_ip(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda hostname, port: _addrinfo("93.184.216.34", "127.0.0.1"),
    )

    error = validate_webhook_url("https://example.com/hook")

    assert error == "url resolves to a blocked address (127.0.0.1)"


def test_validate_webhook_url_accepts_public_resolved_ips(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda hostname, port: _addrinfo(
            "93.184.216.34",
            "2606:2800:220:1:248:1893:25c8:1946",
        ),
    )

    assert validate_webhook_url("https://example.com/hook") is None


# ---------------------------------------------------------------------------
# FIX(#7063): large_tx polling now hits /wallet/balances/all with X-Admin-Key
# ---------------------------------------------------------------------------


def _make_poller(tmp_path, admin_key="secret-admin-key", balances_path="/wallet/balances/all"):
    store = SubscriberStore(db_path=str(tmp_path / "subs.db"))
    return RustChainPoller(
        node_url="http://node.local:5000",
        store=store,
        poll_interval=60,
        large_tx_threshold=5.0,
        admin_key=admin_key,
        balances_path=balances_path,
    )


def test_check_large_tx_skips_when_admin_key_unset(tmp_path, monkeypatch):
    poller = _make_poller(tmp_path, admin_key="")
    calls = []

    def fail_get(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("_get must not be called when admin key is empty")

    monkeypatch.setattr(poller, "_get", fail_get)
    poller._check_large_tx()
    assert calls == []


def test_check_large_tx_uses_new_endpoint_with_admin_key_header(tmp_path, monkeypatch):
    poller = _make_poller(tmp_path)

    captured = {}

    def fake_get(path, headers=None):
        captured["path"] = path
        captured["headers"] = headers
        return {"balances": [], "total_i64": 0, "total_rtc": 0.0}

    monkeypatch.setattr(poller, "_get", fake_get)
    poller._check_large_tx()

    assert captured["path"] == "/wallet/balances/all"
    assert captured["headers"] == {"X-Admin-Key": "secret-admin-key"}


def test_check_large_tx_uses_custom_balances_path(tmp_path, monkeypatch):
    poller = _make_poller(tmp_path, balances_path="/v2/balances")

    captured = {}

    def fake_get(path, headers=None):
        captured["path"] = path
        return {"balances": []}

    monkeypatch.setattr(poller, "_get", fake_get)
    poller._check_large_tx()

    assert captured["path"] == "/v2/balances"


def test_check_large_tx_handles_envelope_response_format(tmp_path, monkeypatch):
    poller = _make_poller(tmp_path)
    response = {
        "balances": [
            {"miner_id": "alpha", "amount_i64": 1_000_000_000, "amount_rtc": 1.0},
            {"miner_id": "beta", "amount_i64": 2_000_000_000, "amount_rtc": 2.0},
            {"miner_id": "gamma", "amount_i64": 5_000_000_000, "amount_rtc": 5.0},
        ],
        "total_i64": 8_000_000_000,
        "total_rtc": 8.0,
    }
    monkeypatch.setattr(poller, "_get", lambda *a, **kw: response)

    poller._check_large_tx()

    # First poll: no previous snapshot, nothing dispatched, but internal
    # state should now hold the new balances.
    assert poller._prev_balances == {"alpha": 1.0, "beta": 2.0, "gamma": 5.0}


def test_check_large_tx_dispatches_event_when_threshold_exceeded(tmp_path, monkeypatch):
    poller = _make_poller(tmp_path)
    poller._prev_balances = {"alpha": 1.0, "beta": 2.0}

    # beta grew by 10 RTC (well over the 5 RTC threshold).
    response = {
        "balances": [
            {"miner_id": "alpha", "amount_rtc": 1.0},
            {"miner_id": "beta", "amount_rtc": 12.0},
        ],
    }
    monkeypatch.setattr(poller, "_get", lambda *a, **kw: response)

    dispatched = []

    def fake_dispatch(event, store):
        dispatched.append(event)

    monkeypatch.setattr("webhook_server.dispatch_event", fake_dispatch)
    poller._check_large_tx()

    assert len(dispatched) == 1
    evt = dispatched[0]
    assert isinstance(evt, WebhookEvent)
    assert evt.event_type == "large_tx"
    assert evt.data["miner"] == "beta"
    assert evt.data["previous_balance"] == 2.0
    assert evt.data["new_balance"] == 12.0
    assert evt.data["delta"] == 10.0
    assert evt.data["direction"] == "credit"


def test_check_large_tx_dispatches_debit_event(tmp_path, monkeypatch):
    poller = _make_poller(tmp_path, balances_path="/wallet/balances/all")
    poller._prev_balances = {"alpha": 100.0}

    response = {
        "balances": [
            {"miner_id": "alpha", "amount_rtc": 50.0},
        ],
    }
    monkeypatch.setattr(poller, "_get", lambda *a, **kw: response)

    dispatched = []
    monkeypatch.setattr("webhook_server.dispatch_event", lambda e, s: dispatched.append(e))
    poller._check_large_tx()

    assert len(dispatched) == 1
    assert dispatched[0].data["direction"] == "debit"
    assert dispatched[0].data["delta"] == -50.0


def test_check_large_tx_skips_below_threshold(tmp_path, monkeypatch):
    poller = _make_poller(tmp_path)
    poller._prev_balances = {"alpha": 1.0}

    response = {
        "balances": [
            {"miner_id": "alpha", "amount_rtc": 2.0},  # delta = 1.0, threshold = 5.0
        ],
    }
    monkeypatch.setattr(poller, "_get", lambda *a, **kw: response)

    dispatched = []
    monkeypatch.setattr("webhook_server.dispatch_event", lambda e, s: dispatched.append(e))
    poller._check_large_tx()

    assert dispatched == []


def test_check_large_tx_accepts_legacy_bare_list_response(tmp_path, monkeypatch):
    poller = _make_poller(tmp_path)
    response = [
        {"miner_id": "alpha", "balance": 1.5},
        {"miner_id": "beta", "balance": 2.5},
    ]
    monkeypatch.setattr(poller, "_get", lambda *a, **kw: response)

    poller._check_large_tx()

    assert poller._prev_balances == {"alpha": 1.5, "beta": 2.5}


def test_check_large_tx_ignores_malformed_entries(tmp_path, monkeypatch):
    poller = _make_poller(tmp_path)
    response = {
        "balances": [
            {"miner_id": "alpha", "amount_rtc": 1.0},
            {"miner_id": None, "amount_rtc": 99.0},       # missing id
            {"amount_rtc": 99.0},                         # missing id
            "not-a-dict",                                  # wrong shape
            {"miner_id": "beta", "amount_rtc": "garbage"},  # bad amount
        ],
    }
    monkeypatch.setattr(poller, "_get", lambda *a, **kw: response)

    poller._check_large_tx()

    assert poller._prev_balances == {"alpha": 1.0}


def test_check_large_tx_handles_unexpected_response_shape(tmp_path, monkeypatch):
    poller = _make_poller(tmp_path)

    monkeypatch.setattr(poller, "_get", lambda *a, **kw: "ok")
    poller._check_large_tx()
    assert poller._prev_balances == {}

    monkeypatch.setattr(poller, "_get", lambda *a, **kw: {"foo": "bar"})
    poller._check_large_tx()
    assert poller._prev_balances == {}


def test_check_large_tx_handles_http_error(tmp_path, monkeypatch):
    poller = _make_poller(tmp_path)
    monkeypatch.setattr(poller, "_get", lambda *a, **kw: None)
    poller._check_large_tx()
    assert poller._prev_balances == {}
