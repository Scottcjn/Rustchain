from pathlib import Path


HTML = (Path(__file__).resolve().parents[1] / "static" / "bridge" / "dashboard.html").read_text(encoding="utf-8")


def test_static_bridge_dashboard_rejects_html_404_responses():
    assert "contentType.includes('application/json')" in HTML
    assert "throw new Error(`Unexpected response from ${url}: ${resp.status}`);" in HTML


def test_static_bridge_dashboard_uses_public_wallet_fallbacks_not_mock_transactions():
    assert "/wallet/balance?miner_id=bridge-escrow" in HTML
    assert "/wallet/history?miner_id=bridge-escrow&limit=50" in HTML
    assert "return { locks: [] };" in HTML
    assert "return { locks: MOCK_DATA.transactions };" not in HTML


def test_static_bridge_dashboard_renders_fetched_stats_and_empty_live_transactions():
    assert "updateStats(stats);" in HTML
    assert "updateFees(stats);" in HTML
    assert "updateTransactions(ledger.locks || []);" in HTML
    assert "updateTransactions(ledger.locks || MOCK_DATA.transactions);" not in HTML
