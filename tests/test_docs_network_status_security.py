from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
HTML_FILES = [
    REPO_ROOT / "docs" / "network-status.html",
    REPO_ROOT / "website" / "static" / "network-status.html",
]


def sources():
    return [path.read_text(encoding="utf-8-sig") for path in HTML_FILES]


def test_network_status_public_copies_stay_synchronized():
    assert sources()[0] == sources()[1]


def test_network_status_defines_html_escaping_helpers():
    for html in sources():
        assert "function escapeHtml(s)" in html
        assert "function safeText(value, fallback = '-')" in html
        assert "function el(tag, className = '', text)" in html


def test_node_cards_render_api_and_error_fields_as_text():
    for html in sources():
        assert "function renderNodeCard(card, base, ok, detailText)" in html
        assert "function renderNodeChecking(card, base)" in html
        assert "node.textContent = String(text ?? '-');" in html
        assert "card.replaceChildren(" in html
        assert "renderNodeChecking(card, base);" in html
        assert "renderNodeCard(card, base, ok, `version: ${health.version ?? '-'}`);" in html
        assert "renderNodeCard(card, base, false, e.message || e);" in html

        assert "card.innerHTML = `" not in html
        assert "version: ${safeText(health.version)}" not in html
        assert "${safeText(e.message || e)}" not in html


def test_incident_rows_render_local_storage_fields_as_text():
    for html in sources():
        assert "log.replaceChildren(...rows);" in html
        assert "el('span', `font-semibold ${i.type === 'OUTAGE'" in html
        assert "el('span', 'font-mono text-xs', i.node)" in html
        assert "el('div', 'text-sm text-slate-300', i.message)" in html

        assert "log.innerHTML = incidents.slice(0, 30).map" not in html
        assert "${safeText(i.type)}</span>" not in html
        assert "${safeText(i.node)}</span>" not in html
        assert "${safeText(i.message)}</div>" not in html


def test_architecture_breakdown_renders_miner_fields_as_text():
    for html in sources():
        assert "function renderArchitectureRow(arch, n, pct)" in html
        assert "summary.append(el('span', '', arch), el('span', '', `${n} (${pct}%)`));" in html
        assert "fill.style.width = `${pct}%`;" in html
        assert "archList.appendChild(renderArchitectureRow(arch, n, pct));" in html

        assert "<span>${safeText(arch)}</span><span>${safeText(n)} (${pct}%)</span>" not in html
        assert "row.innerHTML = `\n              <div class=\"flex justify-between mb-1\"" not in html


def test_network_status_normalizes_current_miners_api_envelopes():
    for html in sources():
        assert "function normalizeMinerRows(payload)" in html
        assert "payload?.miners || payload?.data || payload?.items || []" in html
        assert "const list = normalizeMinerRows(miners);" in html
        assert "rows.filter(row => row && typeof row === 'object')" in html


def test_network_status_architecture_breakdown_uses_current_miner_fields():
    for html in sources():
        assert "function minerArch(row)" in html
        assert "return row.device_arch || row.arch || row.device_family || row.family || row.machine || 'unknown';" in html
        assert "const key = minerArch(m);" in html
