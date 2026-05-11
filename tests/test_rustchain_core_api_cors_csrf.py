# SPDX-License-Identifier: MIT
"""
Regression tests for RustChain core API CORS and CSRF handling.

The API module is loaded directly because the package path contains a hyphen.
"""

import http.client
import importlib.util
import json
import os
import sys
import threading
from http.server import HTTPServer


def _load_rpc_namespace():
    rpc_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "rips",
        "rustchain-core",
        "api",
        "rpc.py",
    )
    module_name = "rustchain_core_rpc_api_under_test"
    spec = importlib.util.spec_from_file_location(module_name, rpc_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module.__dict__


RPC = _load_rpc_namespace()
ApiRequestHandler = RPC["ApiRequestHandler"]
RustChainApi = RPC["RustChainApi"]
MockNode = RPC["MockNode"]


class _ApiServerFixture:
    def __enter__(self):
        self.node = MockNode()
        ApiRequestHandler.api = RustChainApi(self.node)
        self.server = HTTPServer(("127.0.0.1", 0), ApiRequestHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        return self

    def __exit__(self, exc_type, exc, tb):
        self.server.shutdown()
        self.thread.join(timeout=5)

    def request(self, path, method="GET", body=None, headers=None):
        connection = http.client.HTTPConnection(
            "127.0.0.1",
            self.server.server_port,
            timeout=5,
        )
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        raw_body = response.read()
        headers = dict(response.headers)
        connection.close()
        return response.status, headers, raw_body


def _json_body(raw_body):
    return json.loads(raw_body.decode())


def test_unconfigured_cors_does_not_emit_wildcard_origin(monkeypatch):
    monkeypatch.delenv("RUSTCHAIN_API_ALLOWED_ORIGINS", raising=False)

    with _ApiServerFixture() as server:
        status, headers, raw_body = server.request(
            "/api/stats",
            headers={"Origin": "https://evil.example"},
        )

    assert status == 200
    assert _json_body(raw_body)["success"] is True
    assert headers.get("Access-Control-Allow-Origin") is None


def test_configured_cors_echoes_only_exact_allowed_origin(monkeypatch):
    monkeypatch.setenv("RUSTCHAIN_API_ALLOWED_ORIGINS", "https://app.rustchain.org")

    with _ApiServerFixture() as server:
        status, headers, _ = server.request(
            "/api/stats",
            headers={"Origin": "https://app.rustchain.org"},
        )

    assert status == 200
    assert headers["Access-Control-Allow-Origin"] == "https://app.rustchain.org"
    assert headers["Access-Control-Allow-Origin"] != "*"


def test_state_changing_post_fails_closed_without_configured_csrf(monkeypatch):
    monkeypatch.delenv("RUSTCHAIN_API_CSRF_TOKEN", raising=False)

    with _ApiServerFixture() as server:
        status, _, raw_body = server.request(
            "/api/mine",
            method="POST",
            body=b'{"wallet": "alice"}',
            headers={"Content-Type": "application/json"},
        )

    body = _json_body(raw_body)
    assert status == 400
    assert body["success"] is False
    assert body["error"] == "CSRF token is not configured"


def test_state_changing_rpc_requires_matching_csrf_token(monkeypatch):
    monkeypatch.setenv("RUSTCHAIN_API_CSRF_TOKEN", "secret-token")
    payload = json.dumps({
        "method": "submitProof",
        "params": {"wallet": "alice"},
    }).encode()

    with _ApiServerFixture() as server:
        bad_status, _, bad_body = server.request(
            "/rpc",
            method="POST",
            body=payload,
            headers={"Content-Type": "application/json", "X-CSRF-Token": "wrong"},
        )
        ok_status, _, ok_body = server.request(
            "/rpc",
            method="POST",
            body=payload,
            headers={"Content-Type": "application/json", "X-CSRF-Token": "secret-token"},
        )

    assert bad_status == 400
    assert _json_body(bad_body)["error"] == "Invalid CSRF token"
    assert ok_status == 200
    assert _json_body(ok_body)["success"] is True
