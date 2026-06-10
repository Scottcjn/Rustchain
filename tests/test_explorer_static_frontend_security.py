# SPDX-License-Identifier: MIT

from pathlib import Path


EXPLORER_JS = Path(__file__).resolve().parents[1] / "explorer" / "static" / "js" / "explorer.js"


def source() -> str:
    return EXPLORER_JS.read_text(encoding="utf-8")


def test_explorer_health_and_epoch_rendering_are_sanitized() -> None:
    js = source()

    assert "function safeNumber(num, fallback = 0)" in js
    assert "v${escapeHtml(state.health.version || '2.2.1')}" in js
    assert "const slot = safeNumber(epoch.slot, 0);" in js
    assert "const blocksPerEpoch = Math.max(safeNumber(epoch.blocks_per_epoch, 144), 1);" in js
    assert "const progress = Math.max(0, Math.min(100, (slot / blocksPerEpoch) * 100));" in js
    assert "${formatNumber(slot, 0)}/${formatNumber(blocksPerEpoch, 0)}" in js


def test_explorer_miner_ids_escape_visible_table_text() -> None:
    js = source()

    assert '${escapeHtml(shortenAddress(minerId))}' in js
    assert "${escapeHtml(shortenAddress(miner.miner_id || 'unknown'))}" in js
    assert 'title="${escapeHtml(minerId)}"' in js
    assert 'title="${escapeHtml(miner.miner_id)}"' in js


def test_explorer_old_raw_interpolations_are_absent() -> None:
    js = source()

    forbidden_fragments = [
        "v${state.health.version || '2.2.1'}",
        "const progress = ((epoch.slot || 0) / (epoch.blocks_per_epoch || 144)) * 100;",
        "${formatNumber(epoch.slot || 0, 0)}/${epoch.blocks_per_epoch || 144}",
        'title="${escapeHtml(minerId)}">${shortenAddress(minerId)}</td>',
        'title="${escapeHtml(miner.miner_id)}">${shortenAddress(miner.miner_id || \'unknown\')}</td>',
    ]

    for fragment in forbidden_fragments:
        assert fragment not in js
