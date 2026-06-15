# SPDX-License-Identifier: MIT
from pathlib import Path


SERVER = Path(__file__).resolve().parents[1] / "health-dashboard" / "server.py"


def source():
    return SERVER.read_text(encoding="utf-8")


def test_health_dashboard_defines_frontend_safety_helpers():
    text = source()

    assert "function escapeHtml(value)" in text
    assert "function safeStatus(value)" in text
    assert "function safeNumber(value, fallback = 0)" in text
    assert "let latestStatusByNode = {};" in text


def test_health_dashboard_escapes_node_status_fields_before_inner_html():
    text = source()

    assert "const status = safeStatus(node.status);" in text
    assert "latestStatusByNode = Object.fromEntries(list.map(node => [node.node_id, safeStatus(node.status)]));" in text
    assert 'class="status-badge ${status}"' in text
    assert "${escapeHtml(node.name)}" in text
    assert "${escapeHtml(status)}</span>" in text
    assert "${escapeHtml(node.version)}</div>" in text
    assert "${escapeHtml(activeMiners)}</div>" in text
    assert "#${escapeHtml(currentEpoch)}</div>" in text
    assert "${escapeHtml(node.location)}</div>" in text
    assert "Error: ${escapeHtml(node.error)}" in text

    assert 'class="status-badge ${escapeHtml(node.status)}"' not in text
    assert "${node.name}" not in text
    assert "${node.version}</div>" not in text
    assert "${node.location}</div>" not in text
    assert "Error: ${node.error}" not in text


def test_health_dashboard_escapes_incidents_and_map_titles():
    text = source()

    assert "${escapeHtml(String(incident.incident_type || '').replace('_', ' ').toUpperCase())}" in text
    assert "${escapeHtml(nodeName)}: ${escapeHtml(incident.details)}" in text
    assert "const status = safeStatus(latestStatusByNode[node.id]);" in text
    assert 'title="${escapeHtml(node.name)}: ${escapeHtml(status)}"' in text

    assert "${incident.incident_type.replace('_', ' ').toUpperCase()}" not in text
    assert "${nodeName}: ${incident.details}" not in text
    assert 'title="${node.name}: ${current_status[node.id]?.status || \'unknown\'}"' not in text


def test_health_dashboard_atom_feed_escapes_stored_incident_details():
    text = source()

    assert "from html import escape as xml_escape" in text
    assert "<title>{xml_escape(incident_type)}: {xml_escape(str(node_name))}</title>" in text
    assert "<content type=\"text\">{xml_escape(str(row['details'] or ''))}</content>" in text

    assert "<content type=\"html\">{row['details']}</content>" not in text
    assert "<title>{row['incident_type'].replace('_', ' ').title()}: {node_name}</title>" not in text
