# SPDX-License-Identifier: MIT
from pathlib import Path


JS_PATH = Path(__file__).resolve().parents[1] / "explorer" / "beacon-atlas" / "beacon_atlas.js"


def test_beacon_atlas_escapes_info_panel_rows():
    js = JS_PATH.read_text(encoding="utf-8")

    assert "function escapeHtml(value)" in js
    assert 'tooltip.text(label)' in js
    assert 'tooltip.html(label)' not in js
    assert 'const row = (l, v) => `<div class="row"><span class="label">${escapeHtml(l)}</span><span class="value">${escapeHtml(v)}</span></div>`;' in js
    assert 'd3.select("#info-name").text(asText(d.name, d.id));' in js


def test_beacon_atlas_normalizes_api_values_before_string_methods():
    js = JS_PATH.read_text(encoding="utf-8")

    safe_patterns = [
        'const l = String(f ?? "").toLowerCase();',
        'const id = safeId(firstPresent(m.miner, m.miner_id, m.id), `miner-${index}`);',
        'const id = safeId(firstPresent(a.agent_id, a.id), `agent-${index}`);',
        ': (Array.isArray(data.miners?.miners) ? data.miners.miners : []);',
        ': (Array.isArray(data.agents?.agents) ? data.agents.agents : []);',
        'name: asText(firstPresent(m.miner, m.miner_id, m.id), id),',
        'name: asText(a.name, id),',
        'asText(n.name).toLowerCase().includes(q)',
        'asText(n.id).toLowerCase().includes(q)',
        'const name = asText(d.name, d.id);',
        'if (d.pubkey) html += row("Pubkey", asText(d.pubkey).slice(0, 16) + ',
    ]

    for pattern in safe_patterns:
        assert pattern in js

    unsafe_patterns = [
        "const l = f.toLowerCase();",
        "n.name.toLowerCase().includes(q)",
        "n.id.toLowerCase().includes(q)",
        "d.pubkey.slice(0, 16)",
    ]

    for pattern in unsafe_patterns:
        assert pattern not in js
