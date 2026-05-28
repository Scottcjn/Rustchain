# SPDX-License-Identifier: MIT
from pathlib import Path


WS_EXPLORER = Path(__file__).resolve().parents[1] / "explorer" / "templates" / "ws_explorer.html"


def test_ws_explorer_normalizes_miner_payload_shapes():
    html = WS_EXPLORER.read_text(encoding="utf-8")

    assert "function normalizeMinersPayload(payload)" in html
    assert "Array.isArray(payload)" in html
    assert "Array.isArray(payload?.miners)" in html
    assert "miners.filter(miner => miner && typeof miner === 'object')" in html
    assert "const { count, miners } = normalizeMinersPayload(d);" in html
    assert "const cards = miners.slice(0, 12).map(m => {" in html
    assert "d.miners.slice(0, 12)" not in html


def test_ws_explorer_guards_live_event_payloads():
    html = WS_EXPLORER.read_text(encoding="utf-8")

    safe_patterns = [
        "function asObject(value)",
        "function asText(value, fallback = '?')",
        "function safeNumber(value, fallback = 0)",
        "function normalizeAttestationsPayload(payload)",
        "const payload = asObject(data);",
        "document.getElementById('clients').textContent = safeNumber(payload.connected_clients, 0);",
        "const attestations = normalizeAttestationsPayload(list);",
        "for (const a of attestations.slice(0, 5))",
        "id.textContent = asText(firstPresent(m.miner_id, m.miner, m.id));",
        "hardware.textContent = asText(firstPresent(m.hardware, m.device_arch, m.architecture));",
        "multiplier.textContent = `${safeNumber(m.multiplier, 1.0)}x`;",
        "spanWithText('miner-multi', `${safeNumber(a.multiplier, 1.0)}x`)",
    ]

    for pattern in safe_patterns:
        assert pattern in html

    unsafe_patterns = [
        "data.connected_clients",
        "for (const a of list.slice(0, 5))",
        "m.miner_id || m.miner || m.id || '?'",
        "m.hardware || m.device_arch || m.architecture || '?'",
        "`${m.multiplier || 1.0}x`",
        "`${a.multiplier || 1.0}x`",
    ]

    for pattern in unsafe_patterns:
        assert pattern not in html
