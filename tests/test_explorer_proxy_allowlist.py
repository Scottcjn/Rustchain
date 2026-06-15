# SPDX-License-Identifier: Apache-2.0

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "explorer" / "explorer_server.py"


def load_explorer_server():
    spec = importlib.util.spec_from_file_location("explorer_server_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_proxy_allowlist_accepts_explorer_read_endpoints():
    server = load_explorer_server()

    for endpoint in (
        "health",
        "epoch",
        "api/miners",
        "blocks",
        "api/transactions",
        "hall/leaderboard",
    ):
        assert server.validate_proxy_endpoint(endpoint) == endpoint


def test_proxy_allowlist_rejects_unlisted_and_confused_paths():
    server = load_explorer_server()

    for endpoint in (
        "",
        ".",
        "..",
        "/health",
        "admin/status",
        "internal/metrics",
        "api/admin/status",
        "wallet/wind108369",
        "../health",
        "api/../admin",
        "api//miners",
        "api%2Fminers",
        "%2e%2e/admin",
    ):
        assert server.validate_proxy_endpoint(endpoint) is None


def test_proxy_url_preserves_query_for_allowed_endpoint(monkeypatch):
    server = load_explorer_server()
    monkeypatch.setattr(server, "API_BASE", "https://node.example")

    assert (
        server.build_proxy_url("hall/leaderboard", "limit=10&offset=0")
        == "https://node.example/hall/leaderboard?limit=10&offset=0"
    )


def test_proxy_url_returns_none_for_blocked_endpoint(monkeypatch):
    server = load_explorer_server()
    monkeypatch.setattr(server, "API_BASE", "https://node.example")

    assert server.build_proxy_url("admin/status", "") is None
