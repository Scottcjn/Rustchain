from pathlib import Path


DASHBOARD_HTML = (
    Path(__file__).resolve().parents[1]
    / "dashboards"
    / "miner-dashboard"
    / "index.html"
)


def test_history_and_activity_tables_do_not_render_api_fields_with_inner_html():
    html = DASHBOARD_HTML.read_text(encoding="utf-8")

    assert "tbody.innerHTML = history.map(tx =>" not in html
    assert "<td>${tx.counterparty || '--'}</td>" not in html
    assert "<strong>${minerData.miner}</strong>" not in html
    assert "<td>${minerData.hardware_type}</td>" not in html

    assert "appendTextCell(row, tx.counterparty || '--');" in html
    assert "strong.textContent = minerData.miner || '--';" in html
    assert "appendTextCell(row, minerData.hardware_type || '--');" in html


def test_dashboard_normalizes_current_api_envelopes():
    html = DASHBOARD_HTML.read_text(encoding="utf-8")

    assert "const miners = Array.isArray(payload) ? payload : (payload.miners || payload.data || []);" in html
    assert "return Array.isArray(payload) ? payload : (payload.transactions || payload.history || []);" in html


def test_message_helper_uses_text_content_for_error_text():
    html = DASHBOARD_HTML.read_text(encoding="utf-8")

    assert 'area.innerHTML = `<div class="${type}">${text}</div>`;' not in html
    assert "message.textContent = text;" in html
