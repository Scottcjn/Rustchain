# SPDX-License-Identifier: MIT
"""
Regression tests for malformed POST bodies in rips/rustchain-core/api/rpc.py.

The API module is loaded directly because the package path contains a hyphen.
"""

import importlib.util
import json
import threading
from http.client import HTTPConnection
from http.server import HTTPServer
from pathlib import Path


def _load_rpc_module():
    rpc_path = Path(__file__).resolve().parent / "rips" / "rustchain-core" / "api" / "rpc.py"
    spec = importlib.util.spec_from_file_location("rustchain_rpc_json_test_target", rpc_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RPC = _load_rpc_module()
ApiRequestHandler = RPC.ApiRequestHandler
RustChainApi = RPC.RustChainApi
MockNode = RPC.MockNode


class _ApiServerFixture:
    def __enter__(self):
        self.node = MockNode()
        ApiRequestHandler.api = RustChainApi(self.node)
        self.server = HTTPServer(("127.0.0.1", 0), ApiRequestHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.server.shutdown()
        self.thread.join(timeout=5)

    def post(self, path, body):
        connection = HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        try:
            connection.request(
                "POST",
                path,
                body=body,
                headers={"Content-Type": "application/json"},
            )
            response = connection.getresponse()
            return response.status, json.loads(response.read().decode())
        finally:
            connection.close()


def test_malformed_json_post_returns_400_before_routing():
    with _ApiServerFixture() as server:
        status, body = server.post("/api/mine", b'{"wallet":')

    assert status == 400
    assert body["success"] is False
    assert body["error"] == "Invalid JSON body"


def test_malformed_json_rpc_returns_invalid_json_error():
    with _ApiServerFixture() as server:
        status, body = server.post("/rpc", b'{"method":')

    assert status == 400
    assert body["success"] is False
    assert body["error"] == "Invalid JSON body"
