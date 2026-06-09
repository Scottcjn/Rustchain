from pathlib import Path


HTML = (Path(__file__).resolve().parents[1] / "bridge-dashboard" / "index.html").read_text(
    encoding="utf-8"
)


def test_bridge_dashboard_tx_fields_are_escaped():
    assert "function escapeHtml(value)" in HTML
    assert "${escapeHtml(truncateAddress(tx.lock_id, 8))}" in HTML
    assert "${escapeHtml(truncateAddress(tx.sender_wallet))}" in HTML
    assert "${escapeHtml(truncateAddress(tx.target_wallet, 4))}" in HTML
    assert "${escapeHtml(tx.state)}" in HTML
    assert "${escapeHtml(truncateTxHash(tx.release_tx || tx.tx_hash))}" in HTML
    assert "function safeExplorerUrl(txHash)" in HTML
    assert "encodeURIComponent(hash)" in HTML


def test_bridge_dashboard_no_raw_api_fields_in_inner_html():
    assert "${truncateAddress(tx.lock_id" not in HTML
    assert "${truncateAddress(tx.sender_wallet)}" not in HTML
    assert "${truncateAddress(tx.target_wallet" not in HTML
    assert "${tx.state}</span>" not in HTML
    assert "${truncateTxHash(tx.release_tx" not in HTML
