# SPDX-License-Identifier: MIT
"""Unit tests for the pending transfer operator helper."""

import argparse
import importlib.util
import json
import sys
import urllib.error
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "tools" / "pending_ops.py"


def load_module():
    spec = importlib.util.spec_from_file_location("pending_ops_tool", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_req_builds_json_request_with_admin_header():
    module = load_module()
    captured = {}

    def fake_urlopen(req, timeout, context):
        captured["method"] = req.get_method()
        captured["url"] = req.full_url
        captured["headers"] = dict(req.header_items())
        captured["data"] = req.data
        captured["timeout"] = timeout
        captured["context"] = context
        return FakeResponse({"ok": True})

    with patch.object(module.urllib.request, "urlopen", side_effect=fake_urlopen):
        out = module._req(
            "POST",
            "https://node.example/pending/confirm",
            "admin-secret",
            payload={"force": True},
            insecure=False,
        )

    assert out == {"ok": True}
    assert captured["method"] == "POST"
    assert captured["url"] == "https://node.example/pending/confirm"
    assert captured["headers"]["X-admin-key"] == "admin-secret"
    assert json.loads(captured["data"].decode("utf-8")) == {"force": True}
    assert captured["timeout"] == 30
    assert captured["context"] is None


def test_req_uses_unverified_ssl_context_when_insecure():
    module = load_module()
    marker = object()

    with (
        patch.object(module.ssl, "_create_unverified_context", return_value=marker),
        patch.object(module.urllib.request, "urlopen", return_value=FakeResponse({"ok": True})) as urlopen,
    ):
        assert module._req("GET", "https://node.example/pending/list", "key", insecure=True) == {"ok": True}

    assert urlopen.call_args.kwargs["context"] is marker


def test_cmd_list_formats_status_and_limit_query(capsys):
    module = load_module()
    args = argparse.Namespace(
        node="https://node.example/",
        status="confirmed",
        limit=25,
        admin_key="key",
        insecure=True,
    )

    with patch.object(module, "_req", return_value={"items": [{"id": "p1"}]}) as req:
        assert module.cmd_list(args) == 0

    req.assert_called_once_with(
        "GET",
        "https://node.example/pending/list?status=confirmed&limit=25",
        "key",
        insecure=True,
    )
    assert '"id": "p1"' in capsys.readouterr().out


def test_cmd_confirm_posts_empty_payload(capsys):
    module = load_module()
    args = argparse.Namespace(node="https://node.example/", admin_key="key", insecure=False)

    with patch.object(module, "_req", return_value={"confirmed": 2}) as req:
        assert module.cmd_confirm(args) == 0

    req.assert_called_once_with(
        "POST",
        "https://node.example/pending/confirm",
        "key",
        payload={},
        insecure=False,
    )
    assert '"confirmed": 2' in capsys.readouterr().out


def test_main_requires_admin_key(capsys, monkeypatch):
    module = load_module()
    monkeypatch.delenv("RC_ADMIN_KEY", raising=False)

    assert module.main(["list"]) == 2

    assert "missing --admin-key or RC_ADMIN_KEY" in capsys.readouterr().err


def test_main_reports_http_error(capsys):
    module = load_module()

    class FakeHttpError(urllib.error.HTTPError):
        def read(self):
            return b"denied"

    def raise_http_error(args):
        raise FakeHttpError(args.node, 403, "Forbidden", hdrs=None, fp=None)

    with patch.object(module, "cmd_confirm", side_effect=raise_http_error):
        assert module.main(["--admin-key", "key", "confirm"]) == 1

    assert "HTTP 403: denied" in capsys.readouterr().err
