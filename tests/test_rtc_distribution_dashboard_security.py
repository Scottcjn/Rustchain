from pathlib import Path


DASHBOARD_HTML = (
    Path(__file__).resolve().parents[1]
    / "web"
    / "rtc-distribution-dashboard.html"
)


def test_distribution_dashboard_normalizes_current_miners_api_envelope():
    html = DASHBOARD_HTML.read_text(encoding="utf-8")

    assert "function normalizeMinerRows(payload)" in html
    assert "payload?.miners || payload?.data || payload?.items || []" in html
    assert "const list = normalizeMinerRows(data);" in html
    assert "item.miner || item.miner_id || item.id || item.name" in html
    assert "const list = Array.isArray(data) ? data : data.miners || [];" not in html
    assert "const ids = list.map((item) => item.miner).filter(Boolean);" not in html
