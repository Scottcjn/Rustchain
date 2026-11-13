# SPDX-License-Identifier: MIT
"""Tiny local HTTP server that replays recorded /health fixtures.

Used by the node_probe tests and by the per-monitor impostor tests so every
monitor is exercised end-to-end against the same recorded bodies — including
the HTML-200 SPA case — without touching the network.
"""

import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


def fixture_bytes(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def json_route(fixture_name: str, status: int = 200):
    """(status, content_type, body, delay) route serving a JSON fixture."""
    return (status, "application/json", fixture_bytes(fixture_name), 0)


def html_route(fixture_name: str = "spa_200.html", status: int = 200):
    return (status, "text/html", fixture_bytes(fixture_name), 0)


def text_route(fixture_name: str, status: int = 500):
    return (status, "text/plain", fixture_bytes(fixture_name), 0)


def slow_route(delay: float):
    return (200, "application/json", fixture_bytes("health_ok.json"), delay)


class _Handler(BaseHTTPRequestHandler):
    routes = {}

    def do_GET(self):
        route = self.routes.get(self.path.split("?")[0])
        if route is None:
            body = b'{"error": "not found"}'
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        status, ctype, body, delay = route
        if delay:
            time.sleep(delay)
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # keep test output quiet
        pass


def make_server(routes):
    """Start a fixture server on an ephemeral port. Use as a context manager."""
    handler = type("FixtureHandler", (_Handler,), {"routes": dict(routes)})
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    class _Ctx:
        def __enter__(self):
            self.base_url = f"http://127.0.0.1:{server.server_address[1]}"
            return self

        def __exit__(self, *exc):
            server.shutdown()
            server.server_close()
            return False

    return _Ctx()
