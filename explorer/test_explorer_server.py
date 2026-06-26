# SPDX-License-Identifier: MIT

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("explorer_server.py")


class FakeWriter:
    def __init__(self):
        self.payload = b""

    def write(self, payload):
        self.payload += payload


class FakeHandler:
    def __init__(self, headers):
        self.headers = headers
        self.sent_headers = []
        self.status = None
        self.wfile = FakeWriter()

    def send_response(self, status):
        self.status = status

    def send_header(self, name, value):
        self.sent_headers.append((name, value))

    def end_headers(self):
        return None


def _load_explorer(monkeypatch, origins: str):
    monkeypatch.setenv("EXPLORER_CORS_ORIGINS", origins)
    module_name = f"explorer_server_test_{hash(origins)}"
    spec = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(module_name, None)
    return module


def test_send_json_does_not_emit_wildcard_cors_by_default(monkeypatch):
    module = _load_explorer(monkeypatch, "")
    handler = FakeHandler({"Origin": "https://app.example"})

    module.ExplorerHandler.send_json(handler, {"ok": True})

    assert ("Access-Control-Allow-Origin", "*") not in handler.sent_headers
    assert not any(name == "Access-Control-Allow-Origin" for name, _ in handler.sent_headers)


def test_send_json_echoes_only_configured_cors_origin(monkeypatch):
    module = _load_explorer(monkeypatch, "https://app.example, https://admin.example")
    handler = FakeHandler({"Origin": "https://admin.example"})

    module.ExplorerHandler.send_json(handler, {"ok": True})

    assert ("Access-Control-Allow-Origin", "https://admin.example") in handler.sent_headers
    assert ("Vary", "Origin") in handler.sent_headers


def test_options_omits_cors_headers_for_unconfigured_origin(monkeypatch):
    module = _load_explorer(monkeypatch, "https://app.example")
    handler = FakeHandler({"Origin": "https://other.example"})

    module.ExplorerHandler.do_OPTIONS(handler)

    assert handler.status == 200
    assert not any(name == "Access-Control-Allow-Origin" for name, _ in handler.sent_headers)
