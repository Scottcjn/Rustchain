from pathlib import Path


SERVER = Path(__file__).resolve().parents[1] / "health-dashboard" / "server.py"


def source() -> str:
    return SERVER.read_text(encoding="utf-8")


def test_health_dashboard_escapes_node_and_incident_fields() -> None:
    html = source()

    assert "function escapeHtml(value)" in html
    assert "function escapeAttr(value)" in html
    assert "function safeStatus(value)" in html
    assert "function safeNumber(value, fallback = 0)" in html
    assert "${escapeHtml(node.name)}" in html
    assert "status-badge ${safeStatus(node.status)}" in html
    assert "${escapeHtml(safeStatus(node.status))}" in html
    assert "escapeHtml(safeFixed(node.response_time_ms, 0))" in html
    assert "${escapeHtml(node.version || 'unknown')}" in html
    assert "${escapeHtml(formatDuration(node.uptime_s))}" in html
    assert "${escapeHtml(safeNumber(node.active_miners))}" in html
    assert "${escapeHtml(safeNumber(node.current_epoch))}" in html
    assert "${escapeHtml(node.location)}" in html
    assert "${escapeHtml(node.error)}" in html
    assert "const safeIncidentType = escapeHtml(" in html
    assert "${safeTimestamp}" in html
    assert "${safeNodeName}: ${safeDetails}" in html


def test_health_dashboard_escapes_map_marker_titles() -> None:
    html = source()

    assert "function initMap(nodes = [])" in html
    assert "const nodeStatuses = new Map((Array.isArray(nodes) ? nodes : []).map(node => [" in html
    assert "const safeMarkerTitle = `${escapeAttr(node.name)}: ${escapeAttr(status)}`;" in html
    assert 'title="${safeMarkerTitle}"' in html
    assert "initMap(data.nodes);" in html


def test_health_dashboard_feed_escapes_incident_xml_fields() -> None:
    html = source()

    assert "def xml_escape(value) -> str:" in html
    assert "<title>{xml_escape(incident_title)}</title>" in html
    assert "incident-{xml_escape(row['id'])}" in html
    assert "<published>{xml_escape(row['timestamp'])}</published>" in html
    assert "<updated>{xml_escape(row['timestamp'])}</updated>" in html
    assert '<content type="html">{xml_escape(row[\'details\'])}</content>' in html


def test_health_dashboard_old_raw_interpolations_are_absent() -> None:
    html = source()

    forbidden_fragments = [
        "${node.name}</span>",
        "status-badge ${node.status}",
        "${node.status}</span>",
        "${node.response_time_ms.toFixed(0) + ' ms'",
        "${node.version}</div>",
        "${node.active_miners}</div>",
        "#${node.current_epoch}",
        "${node.location}</div>",
        "Error: ${node.error}",
        "${incident.incident_type.replace('_', ' ').toUpperCase()}",
        "${nodeName}: ${incident.details}",
        'title="${node.name}: ${current_status[node.id]?.status || \'unknown\'}"',
        "current_status[node.id]",
        "<title>{row['incident_type'].replace('_', ' ').title()}: {node_name}</title>",
        '<content type="html">{row[\'details\']}</content>',
    ]

    for fragment in forbidden_fragments:
        assert fragment not in html
