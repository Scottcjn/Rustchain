# SPDX-License-Identifier: MIT

import json
import sys
import threading
import urllib.error
import urllib.request
from contextlib import contextmanager
from http.server import HTTPServer
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tools" / "webhooks"))

import webhook_server


@contextmanager
def webhook_admin_server(tmp_path, admin_key):
    store = webhook_server.SubscriberStore(str(tmp_path / "webhooks.db"))

    class TestWebhookAdminHandler(webhook_server.WebhookAdminHandler):
        pass

    TestWebhookAdminHandler.store = store
    TestWebhookAdminHandler.ADMIN_API_KEY = admin_key

    server = HTTPServer(("127.0.0.1", 0), TestWebhookAdminHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", store
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def request_json(base_url, method, path, body=None, headers=None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        base_url + path,
        data=data,
        method=method,
        headers={
            "Content-Type": "application/json",
            **(headers or {}),
        },
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=5) as response:
            payload = json.loads(response.read().decode())
            return response.status, payload
    except urllib.error.HTTPError as exc:
        payload = json.loads(exc.read().decode())
        return exc.code, payload


def test_webhook_admin_fails_closed_when_key_unconfigured(tmp_path):
    with webhook_admin_server(tmp_path, admin_key="") as (base_url, store):
        status, payload = request_json(
            base_url,
            "POST",
            "/webhooks/subscribe",
            {"id": "sub-1", "url": "https://hooks.example/event"},
        )

        assert status == 503
        assert payload == {"error": "WEBHOOK_ADMIN_API_KEY not configured"}
        assert store.list_all() == []


def test_webhook_health_remains_public_when_key_unconfigured(tmp_path):
    with webhook_admin_server(tmp_path, admin_key="") as (base_url, _store):
        status, payload = request_json(base_url, "GET", "/health")

        assert status == 200
        assert payload == {"status": "ok"}


def test_webhook_admin_requires_configured_key(tmp_path, monkeypatch):
    monkeypatch.setattr(webhook_server, "validate_webhook_url", lambda _url: None)

    with webhook_admin_server(tmp_path, admin_key="expected-admin") as (base_url, store):
        status, payload = request_json(
            base_url,
            "POST",
            "/webhooks/subscribe",
            {"id": "sub-1", "url": "https://hooks.example/event"},
        )
        assert status == 401
        assert payload == {"error": "invalid or missing API key"}

        status, payload = request_json(
            base_url,
            "POST",
            "/webhooks/subscribe",
            {"id": "sub-1", "url": "https://hooks.example/event"},
            headers={"X-Admin-API-Key": "expected-admin"},
        )
        assert status == 201
        assert payload["message"] == "subscribed"
        assert [sub.id for sub in store.list_all()] == ["sub-1"]
