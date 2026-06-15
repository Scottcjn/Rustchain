from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTMLS = [
    ROOT / "docs" / "network-status.html",
    ROOT / "website" / "static" / "network-status.html",
]


def sources():
    return [path.read_text(encoding="utf-8-sig") for path in HTMLS]


def test_network_status_defines_html_escaping_helpers():
    for html in sources():
        assert "function escapeHtml(s)" in html
        assert "function safeText(value, fallback = '-')" in html
        assert "function textEl(tag, className, text)" in html


def test_network_status_copies_stay_synchronized():
    assert sources()[0] == sources()[1]


def test_node_cards_escape_api_and_error_fields():
    for html in sources():
        assert "function renderNodeCard(card, base, status)" in html
        assert "textEl('div', 'font-mono text-xs break-all mb-2', base)" in html
        assert "textEl('div', 'text-xs text-slate-400', `version: ${status.version ?? '-'}`)" in html
        assert "textEl('div', 'text-xs text-slate-400', status.message)" in html
        assert "renderNodeCard(card, base, 'checking');" in html
        assert "renderNodeCard(card, base, { ok, version: health.version });" in html
        assert "renderNodeCard(card, base, { ok: false, message: e.message || e });" in html

        assert "${safeText(base)}</div><div class=\"text-sm\">Checking...</div>" not in html
        assert "version: ${safeText(health.version)}" not in html
        assert "${safeText(e.message || e)}" not in html
        assert "version: ${health.version ?? '-'}" not in html
        assert "${String(e.message || e)}" not in html


def test_incident_rows_escape_local_storage_fields():
    for html in sources():
        assert "function renderIncidentRow(incident)" in html
        assert "incident.type ?? '-'" in html
        assert "incident.node ?? '-'" in html
        assert "incident.message ?? '-'" in html
        assert "log.replaceChildren(...incidents.slice(0, 30).map(renderIncidentRow));" in html

        assert "${safeText(i.type)}</span>" not in html
        assert "${safeText(i.node)}</span>" not in html
        assert "${safeText(i.message)}</div>" not in html
        assert "${i.type}</span>" not in html
        assert "${i.node}</span>" not in html
        assert "${i.message}</div>" not in html


def test_architecture_breakdown_escapes_miner_fields():
    for html in sources():
        assert "function renderArchRow(arch, count, pct)" in html
        assert "header.append(textEl('span', '', arch), textEl('span', '', `${count} (${pct}%)`));" in html
        assert "archList.appendChild(renderArchRow(arch, n, pct));" in html

        assert "<span>${safeText(arch)}</span><span>${safeText(n)} (${pct}%)</span>" not in html
        assert "<span>${arch}</span><span>${n} (${pct}%)</span>" not in html


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
