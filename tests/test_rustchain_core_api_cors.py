# SPDX-License-Identifier: MIT

import importlib.util
from io import BytesIO
from pathlib import Path


def _load_rpc_module():
    path = Path(__file__).resolve().parents[1] / "rips" / "rustchain-core" / "api" / "rpc.py"
    spec = importlib.util.spec_from_file_location("rustchain_core_rpc_api", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _make_handler(rpc, origin=None, csrf_token=None):
    handler = object.__new__(rpc.ApiRequestHandler)
    handler.headers = {}
    if origin:
        handler.headers["Origin"] = origin
    if csrf_token:
        handler.headers["X-CSRF-Token"] = csrf_token
    handler.sent_headers = []
    handler.responses = []
    handler.wfile = BytesIO()

    def send_response(status):
        handler.responses.append(status)

    def send_header(name, value):
        handler.sent_headers.append((name, value))

    handler.send_response = send_response
    handler.send_header = send_header
    handler.end_headers = lambda: None
    return handler


def _header_values(handler, name):
    return [value for header, value in handler.sent_headers if header.lower() == name.lower()]


def test_core_api_does_not_emit_wildcard_cors_by_default(monkeypatch):
    rpc = _load_rpc_module()
    monkeypatch.delenv("RUSTCHAIN_API_ALLOWED_ORIGINS", raising=False)
    handler = _make_handler(rpc, origin="https://evil.example")

    rpc.ApiRequestHandler._send_response(handler, rpc.ApiResponse(success=True, data={"ok": True}))

    assert _header_values(handler, "Access-Control-Allow-Origin") == []
    assert handler.responses == [200]


def test_core_api_ignores_wildcard_allowed_origin(monkeypatch):
    rpc = _load_rpc_module()
    monkeypatch.setenv("RUSTCHAIN_API_ALLOWED_ORIGINS", "*")
    handler = _make_handler(rpc, origin="https://evil.example")

    rpc.ApiRequestHandler._send_response(handler, rpc.ApiResponse(success=True, data={"ok": True}))

    assert _header_values(handler, "Access-Control-Allow-Origin") == []


def test_core_api_reflects_only_explicitly_allowed_origin(monkeypatch):
    rpc = _load_rpc_module()
    monkeypatch.setenv(
        "RUSTCHAIN_API_ALLOWED_ORIGINS",
        "https://wallet.example, https://dashboard.example",
    )
    handler = _make_handler(rpc, origin="https://dashboard.example")

    rpc.ApiRequestHandler._send_response(handler, rpc.ApiResponse(success=True, data={"ok": True}))

    assert _header_values(handler, "Access-Control-Allow-Origin") == ["https://dashboard.example"]
    assert _header_values(handler, "Vary") == ["Origin"]


def test_state_changing_rest_endpoint_requires_configured_csrf_token(monkeypatch):
    rpc = _load_rpc_module()
    monkeypatch.delenv("RUSTCHAIN_API_CSRF_TOKEN", raising=False)
    handler = _make_handler(rpc)

    error = rpc.ApiRequestHandler._csrf_error(handler, "/api/mine", {"wallet": "alice"})

    assert error == "RUSTCHAIN_API_CSRF_TOKEN not configured"


def test_state_changing_rest_endpoint_rejects_missing_csrf_token(monkeypatch):
    rpc = _load_rpc_module()
    monkeypatch.setenv("RUSTCHAIN_API_CSRF_TOKEN", "csrf-secret")
    handler = _make_handler(rpc)

    error = rpc.ApiRequestHandler._csrf_error(handler, "/api/governance/vote", {"proposal_id": "1"})

    assert error == "invalid or missing CSRF token"


def test_state_changing_rest_endpoint_accepts_matching_csrf_token(monkeypatch):
    rpc = _load_rpc_module()
    monkeypatch.setenv("RUSTCHAIN_API_CSRF_TOKEN", "csrf-secret")
    handler = _make_handler(rpc, csrf_token="csrf-secret")

    error = rpc.ApiRequestHandler._csrf_error(handler, "/api/governance/create", {"title": "T"})

    assert error is None


def test_mutating_rpc_method_requires_csrf_token(monkeypatch):
    rpc = _load_rpc_module()
    monkeypatch.setenv("RUSTCHAIN_API_CSRF_TOKEN", "csrf-secret")
    handler = _make_handler(rpc)

    error = rpc.ApiRequestHandler._csrf_error(
        handler,
        "/rpc",
        {"method": "createProposal", "params": {"title": "T"}},
    )

    assert error == "invalid or missing CSRF token"


def test_read_only_rpc_method_does_not_require_csrf_token(monkeypatch):
    rpc = _load_rpc_module()
    monkeypatch.delenv("RUSTCHAIN_API_CSRF_TOKEN", raising=False)
    handler = _make_handler(rpc)

    error = rpc.ApiRequestHandler._csrf_error(handler, "/rpc", {"method": "getStats"})

    assert error is None
