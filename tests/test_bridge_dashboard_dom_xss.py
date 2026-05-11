from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BRIDGE_PAGES = (
    ROOT / "static" / "bridge" / "index.html",
    ROOT / "static" / "bridge" / "dashboard.html",
)


def test_bridge_pages_define_html_and_css_token_escaping():
    for page in BRIDGE_PAGES:
        text = page.read_text(encoding="utf-8")
        assert "function escapeHtml(value)" in text
        assert "function safeCssToken(value)" in text
        assert "replace(/[&<>\"']/g" in text
        assert "replace(/[^a-z0-9_-]/g, '-')" in text


def test_bridge_transaction_fields_are_escaped_before_inner_html_injection():
    dashboard = (ROOT / "static" / "bridge" / "dashboard.html").read_text(encoding="utf-8")
    assert "${escapeHtml(tx.sender_wallet)}" in dashboard
    assert "${escapeHtml(String(tx.lock_id || '').substring(0, 16))}" in dashboard
    assert "${escapeHtml(String(tx.type || '').toUpperCase())}" in dashboard
    assert "${escapeHtml(String(tx.target_chain || '').toUpperCase())}" in dashboard
    assert "${escapeHtml(String(tx.state || '').toUpperCase())}" in dashboard
    assert "${safeCssToken(tx.type)}" in dashboard
    assert "${safeCssToken(tx.target_chain)}" in dashboard
    assert "${safeCssToken(tx.state)}" in dashboard

    index = (ROOT / "static" / "bridge" / "index.html").read_text(encoding="utf-8")
    assert "${escapeHtml(tx.sender_wallet)}" in index
    assert "${escapeHtml(tx.amount_rtc)}" in index
    assert "${escapeHtml(String(tx.lock_id || '').substring(0, 12))}" in index
    assert "${escapeHtml(String(tx.target_chain || '').toUpperCase())}" in index
    assert "${escapeHtml(String(tx.state || '').toUpperCase())}" in index
    assert "${safeCssToken(tx.state)}" in index

