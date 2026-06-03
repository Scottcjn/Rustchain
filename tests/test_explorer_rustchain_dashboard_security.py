# SPDX-License-Identifier: MIT

import importlib.util
from pathlib import Path


RUSTCHAIN_DASHBOARD = (
    Path(__file__).resolve().parents[1] / "explorer" / "rustchain_dashboard.py"
)


def _source() -> str:
    return RUSTCHAIN_DASHBOARD.read_text(encoding="utf-8")


def _load_dashboard_module():
    spec = importlib.util.spec_from_file_location(
        "explorer_rustchain_dashboard_under_test",
        RUSTCHAIN_DASHBOARD,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    module.app.config["TESTING"] = True
    return module


def test_explorer_dashboard_escapes_dynamic_table_fields_and_class_tokens():
    source = _source()

    assert "function escapeHtml(value)" in source
    assert "function safeToken(value, allowed" in source
    assert "const archToken = safeToken(m.arch, archTokens, 'modern');" in source
    assert "badge-${archToken}" in source
    assert "${escapeHtml(m.wallet_short)}" in source
    assert "${escapeHtml(m.arch || 'unknown').toUpperCase()}" in source
    assert "${escapeHtml(m.weight)}x" in source
    assert "${escapeHtml(b.height)}" in source
    assert "${escapeHtml(b.miners_count)} miners" in source
    assert "badge-${m.arch}" not in source
    assert "${m.weight}x" not in source
    assert "${b.height}" not in source


def test_explorer_dashboard_normalizes_api_payloads_before_rendering():
    source = _source()

    safe_patterns = [
        "function safeNumber(value, fallback = 0)",
        "function asArray(value)",
        "function asObject(value)",
        "data = asObject(data);",
        "textContent = safeNumber(data.enrolled_miners);",
        "textContent = safeNumber(data.epoch_pot).toFixed(2);",
        "const systemStats = asObject(data.system_stats);",
        "const activeMiners = asArray(data.active_miners);",
        "No active miners",
        "const recentBlocks = asArray(data.recent_blocks);",
        "No recent blocks",
    ]

    for pattern in safe_patterns:
        assert pattern in source

    unsafe_patterns = [
        "data.epoch_pot.toFixed(2)",
        "data.total_balance.toFixed(2)",
        "data.active_miners.map(m => `",
        "data.recent_blocks.map(b => `",
    ]

    for pattern in unsafe_patterns:
        assert pattern not in source


def test_explorer_dashboard_sanitizes_wallet_search_and_errors():
    source = _source()

    assert "fetch(`/api/wallet/${encodeURIComponent(wallet)}`)" in source
    assert "fetch(`/api/wallet/${wallet}`)" not in source
    assert "const tierToken = safeToken(data.tier" in source
    assert "badge-${tierToken}" in source
    assert "err = escapeHtml(err.message || err);" in source
    assert "document.getElementById('search-result').innerHTML = `<h3>❌ Error</h3><p>${err}</p>`;" in source
    assert "${escapeHtml(wallet)}" in source
    assert '<span class="mono">${wallet}</span>' not in source


def test_explorer_stats_api_does_not_echo_internal_exception_details(monkeypatch):
    dashboard = _load_dashboard_module()

    def fail_connect(*args, **kwargs):
        raise RuntimeError("secret database path: /private/rustchain.db")

    monkeypatch.setattr(dashboard.sqlite3, "connect", fail_connect)

    response = dashboard.app.test_client().get("/api/stats")

    assert response.status_code == 500
    body = response.get_json()
    assert body["error"] == "stats_unavailable"
    assert "secret database path" not in response.get_data(as_text=True)


def test_explorer_wallet_lookup_api_does_not_echo_internal_exception_details(monkeypatch):
    dashboard = _load_dashboard_module()

    def fail_connect(*args, **kwargs):
        raise RuntimeError("secret database path: /private/rustchain.db")

    monkeypatch.setattr(dashboard.sqlite3, "connect", fail_connect)

    response = dashboard.app.test_client().get("/api/wallet/RTCabc123")

    assert response.status_code == 500
    body = response.get_json()
    assert body["error"] == "wallet_lookup_unavailable"
    assert "secret database path" not in response.get_data(as_text=True)
