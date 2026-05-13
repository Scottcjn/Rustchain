# SPDX-License-Identifier: MIT

from __future__ import annotations

import argparse
import importlib.util
import json
import urllib.error
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PENDING_OPS_PATH = REPO_ROOT / "tools" / "pending_ops.py"


def _load_pending_ops():
    spec = importlib.util.spec_from_file_location("pending_ops_under_test", PENDING_OPS_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pending_ops = _load_pending_ops()


class FakeResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_req_builds_json_request_with_admin_header(monkeypatch):
    seen = {}

    def fake_urlopen(req, timeout, context):
        seen["method"] = req.get_method()
        seen["url"] = req.full_url
        seen["data"] = req.data
        seen["headers"] = dict(req.header_items())
        seen["timeout"] = timeout
        seen["context"] = context
        return FakeResponse({"ok": True})

    monkeypatch.setattr(pending_ops.urllib.request, "urlopen", fake_urlopen)

    result = pending_ops._req(
        "post",
        "https://node.test/pending/confirm",
        "admin-secret",
        payload={"force": True},
        insecure=False,
    )

    assert result == {"ok": True}
    assert seen["method"] == "POST"
    assert seen["url"] == "https://node.test/pending/confirm"
    assert json.loads(seen["data"].decode("utf-8")) == {"force": True}
    assert seen["headers"]["X-admin-key"] == "admin-secret"
    assert seen["headers"]["Content-type"] == "application/json"
    assert seen["timeout"] == 30
    assert seen["context"] is None


def test_req_uses_unverified_context_when_insecure(monkeypatch):
    marker = object()
    seen = {}

    monkeypatch.setattr(pending_ops.ssl, "_create_unverified_context", lambda: marker)

    def fake_urlopen(req, timeout, context):
        seen["context"] = context
        return FakeResponse({"ok": True})

    monkeypatch.setattr(pending_ops.urllib.request, "urlopen", fake_urlopen)

    assert pending_ops._req("GET", "https://node.test/pending/list", "key", insecure=True) == {"ok": True}
    assert seen["context"] is marker


def test_cmd_list_formats_url_and_prints_response(monkeypatch, capsys):
    seen = {}

    def fake_req(method, url, admin_key, payload=None, *, insecure):
        seen.update(
            {
                "method": method,
                "url": url,
                "admin_key": admin_key,
                "payload": payload,
                "insecure": insecure,
            }
        )
        return {"items": [{"id": 1}], "status": "pending"}

    monkeypatch.setattr(pending_ops, "_req", fake_req)
    args = argparse.Namespace(
        node="https://node.test/",
        status="confirmed",
        limit=25,
        admin_key="admin-secret",
        insecure=True,
    )

    assert pending_ops.cmd_list(args) == 0
    assert seen == {
        "method": "GET",
        "url": "https://node.test/pending/list?status=confirmed&limit=25",
        "admin_key": "admin-secret",
        "payload": None,
        "insecure": True,
    }
    assert json.loads(capsys.readouterr().out) == {"items": [{"id": 1}], "status": "pending"}


def test_cmd_confirm_posts_empty_payload(monkeypatch, capsys):
    seen = {}

    def fake_req(method, url, admin_key, payload=None, *, insecure):
        seen.update(
            {
                "method": method,
                "url": url,
                "admin_key": admin_key,
                "payload": payload,
                "insecure": insecure,
            }
        )
        return {"confirmed": 2}

    monkeypatch.setattr(pending_ops, "_req", fake_req)
    args = argparse.Namespace(node="https://node.test", admin_key="admin-secret", insecure=False)

    assert pending_ops.cmd_confirm(args) == 0
    assert seen == {
        "method": "POST",
        "url": "https://node.test/pending/confirm",
        "admin_key": "admin-secret",
        "payload": {},
        "insecure": False,
    }
    assert json.loads(capsys.readouterr().out) == {"confirmed": 2}


def test_main_rejects_missing_admin_key(monkeypatch, capsys):
    monkeypatch.delenv("RC_ADMIN_KEY", raising=False)

    assert pending_ops.main(["list"]) == 2

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "missing --admin-key or RC_ADMIN_KEY" in captured.err


def test_main_prints_http_error_body(monkeypatch, capsys):
    class FakeHTTPError(urllib.error.HTTPError):
        def read(self):
            return b'{"error":"denied"}'

    def fake_req(method, url, admin_key, payload=None, *, insecure):
        raise FakeHTTPError(url, 403, "Forbidden", hdrs=None, fp=None)

    monkeypatch.setattr(pending_ops, "_req", fake_req)

    assert pending_ops.main(["--admin-key", "secret", "confirm"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert 'HTTP 403: {"error":"denied"}' in captured.err
