#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

import socket

import webhook_server
from webhook_server import RustChainPoller, validate_webhook_url


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


def test_poller_only_sends_node_admin_key_for_admin_reads(monkeypatch):
    calls = []

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"ok": True}

    def fake_get(url, headers=None, timeout=None):
        calls.append({"url": url, "headers": headers or {}, "timeout": timeout})
        return Response()

    monkeypatch.setattr(webhook_server.requests, "get", fake_get)

    poller = RustChainPoller(
        "https://node.example/",
        store=object(),
        node_admin_key="  node-secret  ",
    )

    assert poller._get("/health") == {"ok": True}
    assert poller._get("/wallet/balances/all", admin=True) == {"ok": True}

    assert calls[0]["url"] == "https://node.example/health"
    assert "X-Admin-Key" not in calls[0]["headers"]
    assert calls[1]["url"] == "https://node.example/wallet/balances/all"
    assert calls[1]["headers"] == {"X-Admin-Key": "node-secret"}
    assert calls[1]["timeout"] == 15


def test_poller_large_tx_uses_wallet_balances_all_envelope(monkeypatch):
    responses = [
        {
            "balances": [
                {"miner_id": "alice", "amount_i64": 1_000_000},
                {"miner_id": "bob", "amount_rtc": 2.0},
            ]
        },
        {
            "balances": [
                {"miner_id": "alice", "amount_i64": 2_500_000},
                {"miner_id": "bob", "amount_rtc": 2.0},
            ]
        },
    ]
    paths = []
    events = []

    def fake_get(path, *, admin=False):
        paths.append((path, admin))
        return responses.pop(0)

    monkeypatch.setattr(webhook_server, "dispatch_event", lambda event, store: events.append(event))

    poller = RustChainPoller(
        "https://node.example",
        store=object(),
        large_tx_threshold=1.0,
    )
    monkeypatch.setattr(poller, "_get", fake_get)

    poller._check_large_tx()
    poller._check_large_tx()

    assert paths == [
        ("/wallet/balances/all", True),
        ("/wallet/balances/all", True),
    ]
    assert len(events) == 1
    assert events[0].event_type == "large_tx"
    assert events[0].data == {
        "miner": "alice",
        "previous_balance": 1.0,
        "new_balance": 2.5,
        "delta": 1.5,
        "direction": "credit",
    }
