# SPDX-License-Identifier: MIT
"""Regression tests for webhook admin API authentication."""

import json
import sys
import threading
import urllib.error
import urllib.request
from contextlib import contextmanager
from http.server import HTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "webhooks"))

import webhook_server  # noqa: E402


@contextmanager
def webhook_admin_server(tmp_path, admin_key):
    handler = type("TestWebhookAdminHandler", (webhook_server.WebhookAdminHandler,), {})
    handler.store = webhook_server.SubscriberStore(str(tmp_path / "webhooks.db"))
    handler.ADMIN_API_KEY = admin_key

    server = HTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", handler.store
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def request_json(base_url, method, path, body=None, headers=None):
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")

    req = urllib.request.Request(f"{base_url}{path}", data=data, method=method)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    for key, value in (headers or {}).items():
        req.add_header(key, value)

    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=5) as response:
            payload = response.read().decode("utf-8")
            return response.status, json.loads(payload)
    except urllib.error.HTTPError as exc:
        payload = exc.read().decode("utf-8")
        return exc.code, json.loads(payload)


def test_management_fails_closed_when_admin_key_is_unset(tmp_path):
    with webhook_admin_server(tmp_path, admin_key="") as (base_url, store):
        status, body = request_json(
            base_url,
            "POST",
            "/webhooks/subscribe",
            body={"id": "attacker", "url": "https://example.com/hook"},
        )

        assert status == 503
        assert body["error"] == "WEBHOOK_ADMIN_API_KEY not configured"
        assert store.list_all() == []


def test_health_remains_public_when_admin_key_is_unset(tmp_path):
    with webhook_admin_server(tmp_path, admin_key="") as (base_url, _store):
        status, body = request_json(base_url, "GET", "/health")

        assert status == 200
        assert body == {"status": "ok"}


def test_management_rejects_missing_or_wrong_key(tmp_path):
    with webhook_admin_server(tmp_path, admin_key="expected-key") as (base_url, _store):
        missing_status, missing_body = request_json(base_url, "GET", "/webhooks")
        wrong_status, wrong_body = request_json(
            base_url,
            "GET",
            "/webhooks",
            headers={"X-Admin-API-Key": "wrong-key"},
        )

        assert missing_status == 401
        assert missing_body["error"] == "invalid or missing API key"
        assert wrong_status == 401
        assert wrong_body["error"] == "invalid or missing API key"


def test_management_rejects_non_ascii_admin_key_header(tmp_path):
    with webhook_admin_server(tmp_path, admin_key="expected-key") as (base_url, _store):
        status, body = request_json(
            base_url,
            "GET",
            "/webhooks",
            headers={"X-Admin-API-Key": "e\u00e9"},
        )

        assert status == 401
        assert body["error"] == "invalid or missing API key"


def test_management_accepts_valid_admin_key(tmp_path):
    with webhook_admin_server(tmp_path, admin_key="expected-key") as (base_url, _store):
        status, body = request_json(
            base_url,
            "GET",
            "/webhooks",
            headers={"X-Admin-API-Key": "expected-key"},
        )

        assert status == 200
        assert body == {"subscribers": []}


def test_management_accepts_authenticated_subscribe(tmp_path, monkeypatch):
    monkeypatch.setattr(webhook_server, "validate_webhook_url", lambda _url: None)

    with webhook_admin_server(tmp_path, admin_key="expected-key") as (base_url, store):
        status, body = request_json(
            base_url,
            "POST",
            "/webhooks/subscribe",
            body={"id": "sub-1", "url": "https://hooks.example/event"},
            headers={"X-Admin-API-Key": "expected-key"},
        )

        assert status == 201
        assert body["message"] == "subscribed"
        assert [sub.id for sub in store.list_all()] == ["sub-1"]
