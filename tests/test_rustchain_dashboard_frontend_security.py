# SPDX-License-Identifier: MIT

import importlib.util
from pathlib import Path


RUSTCHAIN_DASHBOARD = (
    Path(__file__).resolve().parents[1] / "node" / "rustchain_dashboard.py"
)


def _source() -> str:
    return RUSTCHAIN_DASHBOARD.read_text(encoding="utf-8")


def _load_dashboard_module():
    spec = importlib.util.spec_from_file_location(
        "rustchain_dashboard_under_test",
        RUSTCHAIN_DASHBOARD,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    module.app.config["TESTING"] = True
    return module


def test_dashboard_escapes_api_fields_before_inner_html_rendering():
    source = _source()

    assert "function escapeHtml(value)" in source
    assert "${escapeHtml(m.wallet_short)}" in source
    assert "${escapeHtml(m.arch || 'unknown').toUpperCase()}" in source
    assert "${escapeHtml(m.last_seen)}" in source
    assert "${escapeHtml(m.age_on_network || 'New')}" in source
    assert "${escapeHtml(b.hash_short)}" in source
    assert "${escapeHtml(b.timestamp)}" in source

    assert "${m.wallet_short}" not in source
    assert "badge-${m.arch}" not in source
    assert "${b.hash_short}" not in source
    assert "${b.timestamp}" not in source


def test_dashboard_sanitizes_dynamic_class_tokens_and_wallet_search():
    source = _source()

    assert "function safeToken(value, allowed" in source
    assert "const archToken = safeToken(m.arch, archTokens, 'modern');" in source
    assert "badge-${archToken}" in source
    assert "const tierToken = safeToken(data.tier" in source
    assert "badge-${tierToken}" in source
    assert "fetch(`/api/wallet/${encodeURIComponent(wallet)}`)" in source
    assert "fetch(`/api/wallet/${wallet}`)" not in source


def test_dashboard_escapes_search_result_and_error_text():
    source = _source()

    assert "${escapeHtml(data.wallet)}" in source
    assert "${escapeHtml(data.balance)}" in source
    assert "${escapeHtml(data.weight)}" in source
    assert "${escapeHtml(data.tier)}" in source
    assert "${escapeHtml(wallet)}" in source
    assert "err = escapeHtml(err.message || err);" in source

    assert "${data.wallet}" not in source
    assert "${data.balance}" not in source
    assert "${data.weight}" not in source
    assert "${data.tier}" not in source
    assert '<span class="mono">${wallet}</span>' not in source


def test_stats_api_does_not_echo_internal_exception_details(monkeypatch):
    dashboard = _load_dashboard_module()

    def fail_connect(*args, **kwargs):
        raise RuntimeError("secret database path: /private/rustchain.db")

    monkeypatch.setattr(dashboard.sqlite3, "connect", fail_connect)

    response = dashboard.app.test_client().get("/api/stats")

    assert response.status_code == 500
    body = response.get_json()
    assert body["error"] == "stats_unavailable"
    assert "secret database path" not in response.get_data(as_text=True)


def test_wallet_lookup_api_does_not_echo_internal_exception_details(monkeypatch):
    dashboard = _load_dashboard_module()

    def fail_connect(*args, **kwargs):
        raise RuntimeError("secret database path: /private/rustchain.db")

    monkeypatch.setattr(dashboard.sqlite3, "connect", fail_connect)

    response = dashboard.app.test_client().get("/api/wallet/RTCabc123")

    assert response.status_code == 500
    body = response.get_json()
    assert body["error"] == "wallet_lookup_unavailable"
    assert "secret database path" not in response.get_data(as_text=True)
