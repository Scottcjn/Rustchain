from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATUS_PAGE = ROOT / "static" / "status" / "index.html"


def _source() -> str:
    return STATUS_PAGE.read_text(encoding="utf-8")


def test_status_dashboard_defines_html_escaping():
    source = _source()
    assert "function escapeHtml(value)" in source
    assert "replace(/[&<>\"']/g" in source
    assert "'&': '&amp;'" in source
    assert "'<': '&lt;'" in source
    assert "'>': '&gt;'" in source
    assert "'\"': '&quot;'" in source
    assert '"\'": \'&#39;\'' in source


def test_status_dashboard_escapes_node_status_fields_before_inner_html():
    source = _source()
    assert "${escapeHtml(node.name)}" in source
    assert "${escapeHtml(node.location)}" in source
    assert "${escapeHtml(String(node.status || '').toUpperCase())}" in source
    assert "${escapeHtml(node.latency_ms || '--')}ms" in source
    assert "${escapeHtml(node.version || 'unknown')}" in source
    assert "${escapeHtml(node.epoch || '--')}" in source
    assert "${escapeHtml(node.miners || 0)}" in source

