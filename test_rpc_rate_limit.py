# SPDX-License-Identifier: MIT
"""
Regression tests for core API rate limiting in rips/rustchain-core/api/rpc.py.

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
    spec = importlib.util.spec_from_file_location("rustchain_rpc_rate_limit_test_target", rpc_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RPC = _load_rpc_module()
ApiRequestHandler = RPC.ApiRequestHandler
RustChainApi = RPC.RustChainApi
MockNode = RPC.MockNode


class _ApiServerFixture:
    def __enter__(self):
        ApiRequestHandler.rate_limiter.reset()
        ApiRequestHandler.api = RustChainApi(MockNode())
        self.server = HTTPServer(("127.0.0.1", 0), ApiRequestHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.server.shutdown()
        self.thread.join(timeout=5)
        ApiRequestHandler.rate_limiter.reset()

    def get(self, path, headers=None):
        connection = HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        try:
            connection.request("GET", path, headers=headers or {})
            response = connection.getresponse()
            return response.status, json.loads(response.read().decode()), response.headers
        finally:
            connection.close()


def _make_handler(client_ip):
    handler = object.__new__(ApiRequestHandler)
    handler.headers = {}
    handler.client_address = (client_ip, 12345)
    return handler


def test_core_api_returns_429_after_per_ip_limit_is_exhausted():
    with patch.dict(
        os.environ,
        {
            "RUSTCHAIN_API_RATE_LIMIT_PER_MINUTE": "2",
            "RUSTCHAIN_API_RATE_LIMIT_BURST": "0",
        },
        clear=True,
    ):
        with _ApiServerFixture() as server:
            first_status, first_body, _ = server.get("/api/stats")
            second_status, second_body, _ = server.get("/api/stats")
            limited_status, limited_body, limited_headers = server.get("/api/stats")

    assert first_status == 200
    assert first_body["success"] is True
    assert second_status == 200
    assert second_body["success"] is True
    assert limited_status == 429
    assert limited_body["success"] is False
    assert limited_body["error"] == "rate_limited"
    assert limited_body["data"]["retry_after_seconds"] >= 1
    assert limited_headers["Retry-After"] == str(limited_body["data"]["retry_after_seconds"])


def test_rate_limit_buckets_are_per_client_ip():
    with patch.dict(
        os.environ,
        {
            "RUSTCHAIN_API_RATE_LIMIT_PER_MINUTE": "1",
            "RUSTCHAIN_API_RATE_LIMIT_BURST": "0",
        },
        clear=True,
    ):
        ApiRequestHandler.rate_limiter.reset()
        first = _make_handler("192.0.2.10")
        second = _make_handler("198.51.100.20")

        assert ApiRequestHandler._rate_limit_error(first) is None
        assert ApiRequestHandler._rate_limit_error(first) is not None
        assert ApiRequestHandler._rate_limit_error(second) is None
        ApiRequestHandler.rate_limiter.reset()


def test_configured_api_key_uses_higher_rate_limit_bucket():
    with patch.dict(
        os.environ,
        {
            "RUSTCHAIN_API_KEY": "trusted-key",
            "RUSTCHAIN_API_RATE_LIMIT_PER_MINUTE": "1",
            "RUSTCHAIN_API_RATE_LIMIT_BURST": "0",
            "RUSTCHAIN_API_KEY_RATE_LIMIT_PER_MINUTE": "2",
        },
        clear=True,
    ):
        ApiRequestHandler.rate_limiter.reset()
        handler = _make_handler("203.0.113.30")
        handler.headers = {"X-RustChain-API-Key": "trusted-key"}

        assert ApiRequestHandler._rate_limit_error(handler) is None
        assert ApiRequestHandler._rate_limit_error(handler) is None
        assert ApiRequestHandler._rate_limit_error(handler) is not None
        ApiRequestHandler.rate_limiter.reset()
