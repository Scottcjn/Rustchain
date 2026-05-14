from pathlib import Path


def test_status_dashboard_defines_render_safety_helpers():
    page = Path(__file__).resolve().parents[1] / "static" / "status" / "index.html"
    html = page.read_text(encoding="utf-8")

    assert "function escapeHtml(value)" in html
    assert "function safeStatus(value)" in html
    assert "function safeNumber(value, fallback = '--')" in html


def test_status_dashboard_escapes_node_status_fields_before_inner_html():
    page = Path(__file__).resolve().parents[1] / "static" / "status" / "index.html"
    html = page.read_text(encoding="utf-8")

    safe_patterns = [
        "const status = safeStatus(node.status);",
        "const statusColor = status === 'up' ? 'var(--green)' : 'var(--red)';",
        "return found ? safeStatus(found.status) === 'up' : false;",
        'class="status-dot ${status}"',
        "${escapeHtml(node.name)}",
        '<div class="location">${escapeHtml(node.location)}</div>',
        "${escapeHtml(status.toUpperCase())}",
        "${escapeHtml(safeNumber(node.latency_ms))}ms",
        "${escapeHtml(node.version || 'unknown')}",
        "${escapeHtml(safeNumber(node.epoch))}",
        "${escapeHtml(safeNumber(node.miners, 0))}",
    ]

    for pattern in safe_patterns:
        assert pattern in html

    unsafe_patterns = [
        "${node.name}",
        "${node.location}",
        "${node.status.toUpperCase()}",
        "${node.latency_ms || '--'}ms",
        "${node.version || 'unknown'}",
        "${node.epoch || '--'}",
        "${node.miners || 0}",
        "found.status === 'up'",
    ]

    for pattern in unsafe_patterns:
        assert pattern not in html
