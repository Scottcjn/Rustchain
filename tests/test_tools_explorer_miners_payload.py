from pathlib import Path


EXPLORER_HTML = (
    Path(__file__).resolve().parents[1]
    / "tools"
    / "explorer"
    / "index.html"
)


def test_tools_explorer_normalizes_current_miners_api_envelope():
    html = EXPLORER_HTML.read_text(encoding="utf-8")

    assert "function normalizeMinerRows(payload)" in html
    assert "payload?.miners || payload?.data || payload?.items || []" in html
    assert "miner: m.miner || m.miner_id || m.id || m.name || \"\"" in html
    assert "state.miners = normalizeMinerRows(miners);" in html
    assert "state.miners = Array.isArray(miners) ? miners : (miners.miners || miners.data || []);" not in html
