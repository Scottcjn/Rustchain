from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
NETWORK_STATUS_HTML = [
    ROOT / "docs" / "network-status.html",
    ROOT / "website" / "static" / "network-status.html",
]


@pytest.fixture(params=NETWORK_STATUS_HTML, ids=lambda path: str(path.relative_to(ROOT)))
def html(request):
    return request.param.read_text(encoding="utf-8-sig")


def test_network_status_defines_text_rendering_helpers(html):
    assert "function escapeHtml(s)" in html
    assert "function safeText(value, fallback = '-')" in html
    assert "function textEl(tag, className, text)" in html
    assert "el.textContent = String(text);" in html
    assert "function renderNodeCard(card, base, status, detail)" in html
    assert "function renderIncidentRow(incident)" in html
    assert "function renderArchRow(arch, count, pct)" in html


def test_node_cards_render_api_and_error_fields_with_text_nodes(html):
    assert "card.innerHTML = `<div class=\"font-mono text-xs break-all mb-2\">${safeText(base)}</div><div class=\"text-sm\">Checking...</div>`" not in html
    assert "version: ${safeText(health.version)}" not in html
    assert "${safeText(e.message || e)}" not in html
    assert "${String(e.message || e)}" not in html

    assert "card.replaceChildren(nodeTitle(base), textEl('div', 'text-sm', 'Checking...'));" in html
    assert "renderNodeCard(card, base, ok ? 'UP' : 'DOWN', `version: ${health.version ?? '-'}`);" in html
    assert "renderNodeCard(card, base, 'DOWN', e.message || e);" in html


def test_incident_rows_render_local_storage_fields_with_text_nodes(html):
    assert "log.innerHTML = incidents.slice(0, 30).map" not in html
    assert "${safeText(i.type)}</span>" not in html
    assert "${safeText(i.node)}</span>" not in html
    assert "${safeText(i.message)}</div>" not in html
    assert "${i.type}</span>" not in html
    assert "${i.node}</span>" not in html
    assert "${i.message}</div>" not in html

    assert "log.replaceChildren(...incidents.slice(0, 30).map(renderIncidentRow));" in html
    assert "row.append(headline, textEl('div', 'text-sm text-slate-300', incident.message));" in html


def test_architecture_breakdown_renders_miner_fields_with_text_nodes(html):
    assert "<span>${safeText(arch)}</span><span>${safeText(n)} (${pct}%)</span>" not in html
    assert "<span>${arch}</span><span>${n} (${pct}%)</span>" not in html

    assert "top.append(textEl('span', '', arch), textEl('span', '', `${count} (${pct}%)`));" in html
    assert "archList.appendChild(renderArchRow(arch, n, pct));" in html


def test_network_status_normalizes_current_miners_api_envelopes(html):
    assert "function normalizeMinerRows(payload)" in html
    assert "payload?.miners || payload?.data || payload?.items || []" in html
    assert "const list = normalizeMinerRows(miners);" in html
    assert "rows.filter(row => row && typeof row === 'object')" in html


def test_network_status_architecture_breakdown_uses_current_miner_fields(html):
    assert "function minerArch(row)" in html
    assert "return row.device_arch || row.arch || row.device_family || row.family || row.machine || 'unknown';" in html
    assert "const key = minerArch(m);" in html


def test_docs_and_static_network_status_stay_in_sync():
    docs, static = [path.read_text(encoding="utf-8-sig") for path in NETWORK_STATUS_HTML]

    assert docs == static
