# SPDX-License-Identifier: MIT
"""Regression tests for the keeper explorer proxy allowlist (Issue #4904).

The previous ``/api/proxy/<path:path>`` implementation forwarded any
path to ``NODE_API`` without validation, exposing an unauthenticated
SSRF vector that reached internal admin endpoints and forwarded raw
upstream headers. These tests prove:

* Disallowed paths return 403 and never call ``requests.get``.
* Allowed read-only paths are forwarded with the safe query
  parameters and the upstream body/status is returned.
* Upstream response headers that leak internal information
  (``Server``, ``Set-Cookie``, ``X-Real-IP`` …) are stripped.
* Query parameters are limited to a small safe character set; keys
  with injection characters are rejected with 403.
"""

import importlib.util
import os
import sys
import tempfile
import types
from pathlib import Path
from unittest.mock import patch

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "keeper_explorer.py"


@pytest.fixture(autouse=True)
def stub_flask_cors(monkeypatch):
    flask_cors = types.ModuleType("flask_cors")
    flask_cors.CORS = lambda *args, **kwargs: None
    monkeypatch.setitem(sys.modules, "flask_cors", flask_cors)


def _load_keeper_explorer(workdir=None):
    """Import keeper_explorer.py with the optional workdir as cwd."""
    if workdir is None:
        workdir_obj = tempfile.TemporaryDirectory()
        workdir = workdir_obj.name
    else:
        workdir_obj = None

    flask_cors = types.ModuleType("flask_cors")
    flask_cors.CORS = lambda *args, **kwargs: None
    sys.modules["flask_cors"] = flask_cors

    old_cwd = None
    try:
        if workdir:
            os.chdir(workdir)
        module_name = "_keeper_explorer_under_test_4904"
        spec = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
        finally:
            sys.modules.pop(module_name, None)
    finally:
        if old_cwd is not None and workdir is not None:
            os.chdir(old_cwd)
    if workdir_obj is not None:
        workdir_obj.cleanup()
    return module


# ---------------------------------------------------------------------------
# validate_proxy_endpoint unit tests
# ---------------------------------------------------------------------------


def test_validate_proxy_endpoint_accepts_allowed_read_only_paths():
    keeper = _load_keeper_explorer()
    for endpoint in (
        "health",
        "epoch",
        "api/miners",
        "blocks",
        "api/transactions",
        "hall/leaderboard",
    ):
        assert keeper.validate_proxy_endpoint(endpoint) == endpoint, endpoint


def test_validate_proxy_endpoint_rejects_unlisted_and_confused_paths():
    keeper = _load_keeper_explorer()
    for endpoint in (
        "",
        ".",
        "..",
        "/health",
        "admin/status",
        "wallet/transfer",
        "healthz",
        "api/miners/../admin",
        "health/../admin",
        "blocks/..",
        "../admin",
    ):
        assert keeper.validate_proxy_endpoint(endpoint) is None, f"failed reject: {endpoint}"


def test_validate_proxy_endpoint_rejects_non_string_inputs():
    keeper = _load_keeper_explorer()
    for endpoint in (None, 123, ["health"], {"path": "health"}):
        assert keeper.validate_proxy_endpoint(endpoint) is None, f"failed reject: {endpoint!r}"


# ---------------------------------------------------------------------------
# _safe_proxy_headers unit tests
# ---------------------------------------------------------------------------


def test_safe_proxy_headers_strips_internal_info():
    keeper = _load_keeper_explorer()
    headers = [
        ("Server", "nginx/1.0"),
        ("Set-Cookie", "session=secret"),
        ("X-Real-IP", "10.0.0.5"),
        ("X-Forwarded-For", "10.0.0.5"),
        ("X-Cache", "MISS"),
        ("Content-Type", "application/json"),
    ]
    safe = keeper._safe_proxy_headers(headers)
    safe_names = {name for name, _ in safe}
    assert "Content-Type" in safe_names
    for stripped in ("Server", "Set-Cookie", "X-Real-IP", "X-Forwarded-For", "X-Cache"):
        assert stripped not in safe_names, f"{stripped} leaked through _safe_proxy_headers"


def test_safe_proxy_headers_handles_case_insensitively():
    keeper = _load_keeper_explorer()
    headers = [("server", "x"), ("SERVER", "y"), ("X-Real-IP", "1.1.1.1")]
    safe = keeper._safe_proxy_headers(headers)
    assert safe == []


def test_safe_proxy_headers_preserves_content_negotiation():
    keeper = _load_keeper_explorer()
    headers = [("Content-Type", "application/json"), ("Content-Length", "12345")]
    safe = keeper._safe_proxy_headers(headers)
    assert ("Content-Type", "application/json") in safe
    assert ("Content-Length", "12345") in safe


# ---------------------------------------------------------------------------
# /api/proxy/<path:path> route tests
# ---------------------------------------------------------------------------


def _make_upstream(content, status, header_pairs):
    return types.SimpleNamespace(
        content=content,
        status_code=status,
        headers=types.SimpleNamespace(items=lambda h=header_pairs: list(h)),
    )


def test_proxy_rejects_unlisted_path_without_calling_requests(tmp_path, monkeypatch):
    keeper = _load_keeper_explorer(tmp_path)
    monkeypatch.chdir(tmp_path)

    with patch.object(keeper, "requests") as mock_requests:
        response = keeper.app.test_client().get("/api/proxy/admin/status")

    assert response.status_code == 403
    assert response.get_json() == {"error": "Proxy path not allowed"}
    mock_requests.get.assert_not_called()


def test_proxy_rejects_path_traversal_without_calling_requests(tmp_path, monkeypatch):
    keeper = _load_keeper_explorer(tmp_path)
    monkeypatch.chdir(tmp_path)

    for path in (
        "/api/proxy/api/miners/../admin",
        "/api/proxy/blocks/..",
        "/api/proxy/../admin",
    ):
        with patch.object(keeper, "requests") as mock_requests:
            response = keeper.app.test_client().get(path)
        assert response.status_code == 403, f"expected 403 for {path}, got {response.status_code}"
        mock_requests.get.assert_not_called()


def test_proxy_rejects_dot_segment_path(tmp_path, monkeypatch):
    keeper = _load_keeper_explorer(tmp_path)
    monkeypatch.chdir(tmp_path)

    with patch.object(keeper, "requests") as mock_requests:
        response = keeper.app.test_client().get("/api/proxy/blocks/..%2Fadmin")

    assert response.status_code == 403
    mock_requests.get.assert_not_called()


def test_proxy_rejects_unsafe_query_key(tmp_path, monkeypatch):
    keeper = _load_keeper_explorer(tmp_path)
    monkeypatch.chdir(tmp_path)

    with patch.object(keeper, "requests") as mock_requests:
        # The first query key is safe; the second contains '/' which is not in the allowlist.
        response = keeper.app.test_client().get("/api/proxy/api/miners?a=1&b/c=2")

    assert response.status_code == 403
    mock_requests.get.assert_not_called()


def test_proxy_forwards_allowed_path_with_safe_query(tmp_path, monkeypatch):
    keeper = _load_keeper_explorer(tmp_path)
    monkeypatch.chdir(tmp_path)

    upstream = _make_upstream(
        content=b'{"miners":[]}',
        status=200,
        header_pairs=[
            ("Content-Type", "application/json"),
            ("Server", "rustchain-internal/9.9.9"),
            ("Set-Cookie", "session=secret"),
            ("X-Real-IP", "10.0.0.5"),
            ("X-Forwarded-For", "10.0.0.5"),
            ("X-Cache", "MISS"),
        ],
    )

    with patch.object(keeper, "requests") as mock_requests:
        mock_requests.get.return_value = upstream
        response = keeper.app.test_client().get("/api/proxy/api/miners?limit=10")

    assert response.status_code == 200
    assert response.data == b'{"miners":[]}'

    # Upstream called exactly once with the safe endpoint and safe params
    assert mock_requests.get.call_count == 1
    call_args, call_kwargs = mock_requests.get.call_args
    assert call_args[0].endswith("/api/miners")
    assert call_kwargs["timeout"] == 5
    assert call_kwargs["params"] == [("limit", ["10"])]

    # Sensitive headers are stripped
    forwarded = {name: value for name, value in response.headers.items()}
    assert "Content-Type" in forwarded
    assert "Server" not in forwarded
    assert "Set-Cookie" not in forwarded
    assert "X-Real-IP" not in forwarded
    assert "X-Forwarded-For" not in forwarded
    assert "X-Cache" not in forwarded


def test_proxy_strips_internal_headers_for_all_allowed_paths(tmp_path, monkeypatch):
    keeper = _load_keeper_explorer(tmp_path)
    monkeypatch.chdir(tmp_path)

    upstream = _make_upstream(
        content=b'{"ok":true}',
        status=200,
        header_pairs=[
            ("Content-Type", "application/json"),
            ("Server", "internal/1.0"),
            ("Set-Cookie", "secret"),
            ("X-Internal-IP", "10.1.2.3"),
            ("X-Powered-By", "RustChain/0.1"),
            ("X-AspNet-Version", "4.0"),
            ("Via", "1.1 varnish"),
        ],
    )

    for endpoint in ("health", "epoch", "api/miners", "blocks",
                     "api/transactions", "hall/leaderboard"):
        with patch.object(keeper, "requests") as mock_requests:
            mock_requests.get.return_value = upstream
            response = keeper.app.test_client().get(f"/api/proxy/{endpoint}")
        assert response.status_code == 200
        forwarded = {name.lower() for name, _ in response.headers.items()}
        for stripped in (
            "server",
            "set-cookie",
            "x-internal-ip",
            "x-powered-by",
            "x-aspnet-version",
            "via",
        ):
            assert stripped not in forwarded, (
                f"{stripped} leaked through proxy for {endpoint}"
            )


def test_proxy_returns_502_on_upstream_connection_error(tmp_path, monkeypatch):
    keeper = _load_keeper_explorer(tmp_path)
    monkeypatch.chdir(tmp_path)

    with patch.object(keeper, "requests") as mock_requests:
        mock_requests.get.side_effect = Exception("connection refused")
        response = keeper.app.test_client().get("/api/proxy/health")

    assert response.status_code == 502
    assert response.get_json() == {"error": "Node connection failed"}


def test_proxy_propagates_upstream_status_code(tmp_path, monkeypatch):
    keeper = _load_keeper_explorer(tmp_path)
    monkeypatch.chdir(tmp_path)

    upstream = _make_upstream(
        content=b'{"detail":"upstream says no"}',
        status=503,
        header_pairs=[("Content-Type", "application/json")],
    )

    with patch.object(keeper, "requests") as mock_requests:
        mock_requests.get.return_value = upstream
        response = keeper.app.test_client().get("/api/proxy/blocks")

    assert response.status_code == 503
    assert response.data == b'{"detail":"upstream says no"}'
