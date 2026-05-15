# SPDX-License-Identifier: MIT
"""Unit tests for the lightweight RustChain server proxy."""

import os
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import pytest


NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "node"))
if NODE_DIR not in sys.path:
    sys.path.insert(0, NODE_DIR)

import server_proxy  # noqa: E402


@dataclass
class FakeResponse:
    status_code: int = 200
    payload: Optional[Any] = None
    text: str = ""
    headers: Dict[str, str] = field(default_factory=dict)
    json_error: Optional[Exception] = None

    def json(self):
        if self.json_error is not None:
            raise self.json_error
        return self.payload


@pytest.fixture
def client():
    server_proxy.app.config["TESTING"] = True
    with server_proxy.app.test_client() as test_client:
        yield test_client


def test_status_endpoint_reports_proxy_configuration(client):
    response = client.get("/status")

    assert response.status_code == 200
    assert response.get_json() == {
        "proxy": "active",
        "local_server": server_proxy.LOCAL_SERVER,
        "message": "RustChain proxy for vintage hardware",
    }


def test_home_endpoint_lists_available_proxy_routes(client):
    response = client.get("/")

    assert response.status_code == 200
    body = response.get_json()
    assert body["service"] == "RustChain G4 Proxy"
    assert "/api/register" in body["endpoints"]
    assert "/status" in body["endpoints"]


def test_proxy_get_forwards_path_and_query_params(monkeypatch, client):
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse(
            status_code=202,
            payload={"ok": True},
            headers={"Content-Type": "application/json"},
        )

    monkeypatch.setattr(server_proxy.requests, "get", fake_get)

    response = client.get("/api/stats?limit=10&tag=a&tag=b")

    assert response.status_code == 202
    assert response.get_json() == {"ok": True}
    assert calls == [
        (
            f"{server_proxy.LOCAL_SERVER}/api/stats",
            {"params": {"limit": ["10"], "tag": ["a", "b"]}, "timeout": 10},
        )
    ]


def test_proxy_post_forwards_json_body_query_params_and_headers(monkeypatch, client):
    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse(
            status_code=201,
            payload={"registered": True},
            headers={"Content-Type": "application/json; charset=utf-8"},
        )

    monkeypatch.setattr(server_proxy.requests, "post", fake_post)

    response = client.post("/api/register?dry_run=1", json={"address": "RTC123"})

    assert response.status_code == 201
    assert response.get_json() == {"registered": True}
    assert calls == [
        (
            f"{server_proxy.LOCAL_SERVER}/api/register",
            {
                "json": {"address": "RTC123"},
                "params": {"dry_run": ["1"]},
                "headers": {"Content-Type": "application/json"},
                "timeout": 10,
            },
        )
    ]


def test_proxy_returns_upstream_text_for_non_json_response(monkeypatch, client):
    monkeypatch.setattr(
        server_proxy.requests,
        "get",
        lambda *args, **kwargs: FakeResponse(
            status_code=503,
            text="temporarily unavailable",
            headers={"Content-Type": "text/plain"},
        ),
    )

    response = client.get("/api/stats")

    assert response.status_code == 503
    assert response.get_data(as_text=True) == "temporarily unavailable"


def test_proxy_falls_back_to_text_when_json_body_is_invalid(monkeypatch, client):
    monkeypatch.setattr(
        server_proxy.requests,
        "get",
        lambda *args, **kwargs: FakeResponse(
            status_code=502,
            text="bad gateway",
            headers={"Content-Type": "application/json"},
            json_error=ValueError("invalid json"),
        ),
    )

    response = client.get("/api/stats")

    assert response.status_code == 502
    assert response.get_data(as_text=True) == "bad gateway"


def test_proxy_timeout_maps_to_504(monkeypatch, client):
    def raise_timeout(*args, **kwargs):
        raise server_proxy.requests.exceptions.Timeout("slow upstream")

    monkeypatch.setattr(server_proxy.requests, "get", raise_timeout)

    response = client.get("/api/stats")

    assert response.status_code == 504
    assert response.get_json() == {"error": "Local server timeout"}


def test_proxy_unexpected_request_failure_maps_to_500(monkeypatch, client):
    def raise_failure(*args, **kwargs):
        raise server_proxy.requests.exceptions.ConnectionError("refused")

    monkeypatch.setattr(server_proxy.requests, "get", raise_failure)

    response = client.get("/api/stats")

    assert response.status_code == 500
    assert "refused" in response.get_json()["error"]
