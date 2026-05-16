#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

import socket

from webhook_server import validate_webhook_url


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
