# SPDX-License-Identifier: MIT
"""
Regression tests for malformed POST bodies in rips/rustchain-core/api/rpc.py.

The API module is loaded directly because the package path contains a hyphen.
"""

import json
import os
import threading
import time
from http.server import HTTPServer
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

    def post(self, path, body):
        request = Request(
            f"{self.url}{path}",
            data=body,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read().decode())
        except HTTPError as error:
            return error.code, json.loads(error.read().decode())


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
