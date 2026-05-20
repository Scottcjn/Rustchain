from pathlib import Path


def test_museum_architecture_legend_uses_text_nodes_for_miner_fields():
    script_path = Path(__file__).resolve().parents[1] / "web" / "museum" / "museum.js"
    script = script_path.read_text(encoding="utf-8")

    assert "const legendEntries = entries.slice(0, 6).map(([n, c]) => `${c}x ${n}`);" in script
    assert "legend.appendChild(document.createElement('br'));" in script
    assert "legend.appendChild(document.createTextNode(legendEntries[i]));" in script
    assert "legend.innerHTML = entries.slice(0, 6).map(([n, c]) => `${c}x ${n}`).join('<br>')" not in script


def test_museum_normalizes_current_miners_api_envelope():
    script_path = Path(__file__).resolve().parents[1] / "web" / "museum" / "museum.js"
    script = script_path.read_text(encoding="utf-8")

    assert "function normalizeMinerRows(payload)" in script
    assert "payload?.miners || payload?.data || payload?.items || []" in script
    assert "miner: m.miner || m.miner_id || m.id || m.name || ''" in script
    assert "state.miners = normalizeMinerRows(miners);" in script
    assert "state.miners = Array.isArray(miners) ? miners : (miners?.miners || []);" not in script
