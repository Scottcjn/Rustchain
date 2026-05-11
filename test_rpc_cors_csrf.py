# SPDX-License-Identifier: MIT
"""
Regression tests for API CORS and CSRF handling in rips/rustchain-core/api/rpc.py.

The API module is loaded directly because the package path contains a hyphen.
"""

import json
import os
import threading
from http.server import HTTPServer
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def _load_rpc_namespace():
    rpc_path = os.path.join(
        os.path.dirname(__file__),
        "rips",
        "rustchain-core",
        "api",
        "rpc.py",
    )
    with open(rpc_path) as f:
        source = f.read()

    ns = {"__name__": "__not_main__"}
    exec(compile(source, rpc_path, "exec"), ns)
    return ns


RPC = _load_rpc_namespace()
ApiRequestHandler = RPC["ApiRequestHandler"]
RustChainApi = RPC["RustChainApi"]
MockNode = RPC["MockNode"]


class _ApiServerFixture:
    def __enter__(self):
        ApiRequestHandler.api = RustChainApi(MockNode())
        self.server = HTTPServer(("127.0.0.1", 0), ApiRequestHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        return self

    def __exit__(self, exc_type, exc, tb):
        self.server.shutdown()
        self.thread.join(timeout=5)

    def get(self, path, headers=None):
        request = Request(f"{self.url}{path}", method="GET", headers=headers or {})
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read().decode()), response.headers
        except HTTPError as error:
            return error.code, json.loads(error.read().decode()), error.headers

    def post(self, path, body, headers=None):
        request = Request(
            f"{self.url}{path}",
            data=json.dumps(body).encode(),
            method="POST",
            headers={"Content-Type": "application/json", **(headers or {})},
        )
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read().decode()), response.headers
        except HTTPError as error:
            return error.code, json.loads(error.read().decode()), error.headers


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
