# SPDX-License-Identifier: MIT
"""
Regression tests for API CORS and CSRF handling in rips/rustchain-core/api/rpc.py.

The API module is loaded directly because the package path contains a hyphen.
"""

import importlib.util
import json
import os
import threading
from http.client import HTTPConnection
from http.server import HTTPServer
from pathlib import Path
from unittest.mock import patch


def _load_rpc_module():
    rpc_path = Path(__file__).resolve().parent / "rips" / "rustchain-core" / "api" / "rpc.py"
    spec = importlib.util.spec_from_file_location("rustchain_rpc_test_target", rpc_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RPC = _load_rpc_module()
ApiRequestHandler = RPC.ApiRequestHandler
RustChainApi = RPC.RustChainApi
MockNode = RPC.MockNode


class _ApiServerFixture:
    def __enter__(self):
        ApiRequestHandler.api = RustChainApi(MockNode())
        self.server = HTTPServer(("127.0.0.1", 0), ApiRequestHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.server.shutdown()
        self.thread.join(timeout=5)

    def get(self, path, headers=None):
        connection = HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        try:
            connection.request("GET", path, headers=headers or {})
            response = connection.getresponse()
            return response.status, json.loads(response.read().decode()), response.headers
        finally:
            connection.close()

    def post(self, path, body, headers=None):
        connection = HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        try:
            connection.request(
                "POST",
                path,
                body=json.dumps(body).encode(),
                headers={"Content-Type": "application/json", **(headers or {})},
            )
            response = connection.getresponse()
            return response.status, json.loads(response.read().decode()), response.headers
        finally:
            connection.close()


def test_default_response_does_not_send_wildcard_cors():
    with patch.dict(os.environ, {}, clear=True):
        with _ApiServerFixture() as server:
            status, body, headers = server.get(
                "/api/stats",
                headers={"Origin": "https://evil.example"},
            )

    assert status == 200
    assert body["success"] is True
    assert headers.get("Access-Control-Allow-Origin") is None


def test_configured_origin_is_reflected_in_cors_response():
    with patch.dict(
        os.environ,
        {"RUSTCHAIN_API_ALLOWED_ORIGINS": "https://wallet.example"},
        clear=True,
    ):
        with _ApiServerFixture() as server:
            status, body, headers = server.get(
                "/api/stats",
                headers={"Origin": "https://wallet.example"},
            )

    assert status == 200
    assert body["success"] is True
    assert headers.get("Access-Control-Allow-Origin") == "https://wallet.example"
    assert headers.get("Vary") == "Origin"


def test_browser_state_changing_post_requires_csrf_token():
    with patch.dict(
        os.environ,
        {
            "RUSTCHAIN_API_ALLOWED_ORIGINS": "https://wallet.example",
            "RUSTCHAIN_API_CSRF_TOKEN": "known-token",
        },
        clear=True,
    ):
        with _ApiServerFixture() as server:
            status, body, headers = server.post(
                "/api/mine",
                {"wallet": "RTC1Test"},
                headers={"Origin": "https://wallet.example"},
            )

    assert status == 403
    assert body["success"] is False
    assert body["error"] == "CSRF token required"
    assert headers.get("Access-Control-Allow-Origin") == "https://wallet.example"


def test_browser_state_changing_post_accepts_valid_csrf_token():
    with patch.dict(
        os.environ,
        {
            "RUSTCHAIN_API_ALLOWED_ORIGINS": "https://wallet.example",
            "RUSTCHAIN_API_CSRF_TOKEN": "known-token",
        },
        clear=True,
    ):
        with _ApiServerFixture() as server:
            status, body, headers = server.post(
                "/api/mine",
                {"wallet": "RTC1Test"},
                headers={
                    "Origin": "https://wallet.example",
                    "X-RustChain-CSRF-Token": "known-token",
                },
            )

    assert status == 200
    assert body["success"] is True
    assert headers.get("Access-Control-Allow-Origin") == "https://wallet.example"
