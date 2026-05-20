from pathlib import Path


HTML = Path(__file__).resolve().parents[1] / "docs" / "network-status.html"


def source():
    return HTML.read_text(encoding="utf-8-sig")


def test_network_status_defines_html_escaping_helpers():
    html = source()

    assert "function escapeHtml(s)" in html
    assert "function safeText(value, fallback = '-')" in html


def test_node_cards_escape_api_and_error_fields():
    html = source()

    assert "${safeText(base)}</div><div class=\"text-sm\">Checking...</div>" in html
    assert "version: ${safeText(health.version)}" in html
    assert "${safeText(e.message || e)}" in html
    assert "version: ${health.version ?? '-'}" not in html
    assert "${String(e.message || e)}" not in html


def test_incident_rows_escape_local_storage_fields():
    html = source()

    assert "${safeText(i.type)}</span>" in html
    assert "${safeText(i.node)}</span>" in html
    assert "${safeText(i.message)}</div>" in html
    assert "${i.type}</span>" not in html
    assert "${i.node}</span>" not in html
    assert "${i.message}</div>" not in html


def test_architecture_breakdown_escapes_miner_fields():
    html = source()

    assert "<span>${safeText(arch)}</span><span>${safeText(n)} (${pct}%)</span>" in html
    assert "<span>${arch}</span><span>${n} (${pct}%)</span>" not in html


def test_network_status_normalizes_current_miners_api_envelopes():
    html = source()

    assert "function normalizeMinerRows(payload)" in html
    assert "payload?.miners || payload?.data || payload?.items || []" in html
    assert "const list = normalizeMinerRows(miners);" in html
    assert "rows.filter(row => row && typeof row === 'object')" in html


def test_network_status_architecture_breakdown_uses_current_miner_fields():
    html = source()

    assert "function minerArch(row)" in html
    assert "return row.device_arch || row.arch || row.device_family || row.family || row.machine || 'unknown';" in html
    assert "const key = minerArch(m);" in html
