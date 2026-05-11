from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "node" / "rustchain_dashboard.py"


def _source() -> str:
    return DASHBOARD.read_text(encoding="utf-8")


def test_mining_dashboard_defines_escape_helpers():
    source = _source()
    assert "function escapeHtml(value)" in source
    assert "function safeCssToken(value)" in source
    assert "function formatNumber(value, fractionDigits = null)" in source
    assert "replace(/[&<>\"']/g" in source
    assert "replace(/[^a-z0-9_-]/g, '-')" in source
    assert "Number.isFinite(number)" in source


def test_mining_dashboard_escapes_miner_and_block_rows_before_inner_html():
    source = _source()
    assert "${escapeHtml(m.wallet_short)}" in source
    assert "${safeCssToken(m.arch)}" in source
    assert "${escapeHtml(String(m.arch || '').toUpperCase())}" in source
    assert "${formatNumber(m.weight)}" in source
    assert "${formatNumber(m.balance, 6)}" in source
    assert "${escapeHtml(m.last_seen)}" in source
    assert "${escapeHtml(m.age_on_network || 'New')}" in source

    assert "${formatNumber(b.height)}" in source
    assert "${escapeHtml(b.hash_short)}" in source
    assert "${escapeHtml(b.timestamp)}" in source
    assert "${formatNumber(b.miners_count)}" in source
    assert "${formatNumber(b.reward)}" in source


def test_mining_dashboard_escapes_wallet_search_rendering_and_encodes_route():
    source = _source()
    assert "fetch(`/api/wallet/${encodeURIComponent(wallet)}`)" in source
    assert "${escapeHtml(data.wallet)}" in source
    assert "${formatNumber(data.balance)}" in source
    assert "${formatNumber(data.weight)}" in source
    assert "${escapeHtml(data.tier)}" in source
    assert "${escapeHtml(data.age_on_network || 'Unknown')}" in source
    assert "${escapeHtml(data.last_seen || 'Never')}" in source
    assert "${escapeHtml(wallet)}" in source
    assert "${escapeHtml(err)}" in source


def test_mining_dashboard_no_longer_uses_raw_reviewed_interpolations():
    source = _source()
    raw_interpolations = (
        "${m.weight}x",
        "${m.balance.toFixed(6)}",
        "${b.height}",
        "${b.miners_count}",
        "${b.reward}",
        "${data.balance}",
        "${data.weight}",
        "fetch(`/api/wallet/${wallet}`)",
    )
    for interpolation in raw_interpolations:
        assert interpolation not in source

