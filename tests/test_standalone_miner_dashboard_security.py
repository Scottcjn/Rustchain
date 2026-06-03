from pathlib import Path


DASHBOARD_HTML = (
    Path(__file__).resolve().parents[1]
    / "tools"
    / "miner_dashboard"
    / "index.html"
)


def test_share_link_is_built_with_text_nodes():
    html = DASHBOARD_HTML.read_text(encoding="utf-8")

    assert 'el("shareRow").innerHTML = "Share link:' not in html
    assert 'row.textContent = "Share link: ";' in html
    assert "link.textContent = full;" in html


def test_fleet_rows_do_not_render_api_fields_with_inner_html():
    html = DASHBOARD_HTML.read_text(encoding="utf-8")

    assert '"<td>" + m.machine + "</td>"' not in html
    assert '"<td>" + m.arch + "</td>"' not in html
    assert '"<td>" + (m.badge || "-") + "</td>"' not in html

    assert "function appendTextCell(row, text, className)" in html
    assert "appendTextCell(tr, m.machine);" in html
    assert "appendTextCell(tr, m.arch);" in html
    assert 'appendTextCell(tr, m.badge || "-");' in html


def test_miner_dashboard_normalizes_miner_payload_envelopes():
    html = DASHBOARD_HTML.read_text(encoding="utf-8")

    assert "function normalizeMinerRows(payload)" in html
    assert "Array.isArray(payload?.miners)" in html
    assert "Array.isArray(payload?.data)" in html
    assert "Array.isArray(payload?.items)" in html
    assert "const miners = normalizeMinerRows(minersRes);" in html


def test_miner_dashboard_normalizes_miner_row_ids_before_lookup():
    html = DASHBOARD_HTML.read_text(encoding="utf-8")

    assert "const miner = row.miner || row.miner_id || row.id;" in html
    assert 'return Object.assign({}, row, { miner: String(miner) });' in html
    assert "}).filter(Boolean);" in html
    assert 'String(m.miner || "").toLowerCase() === minerId.toLowerCase()' in html
