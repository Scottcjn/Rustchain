# SPDX-License-Identifier: MIT
from pathlib import Path


EXPLORER_JS = (
    Path(__file__).resolve().parents[1]
    / "explorer"
    / "static"
    / "js"
    / "explorer.js"
)


def source() -> str:
    return EXPLORER_JS.read_text(encoding="utf-8")


def test_explorer_status_bar_escapes_health_version_from_api():
    js = source()

    assert "${state.health ? `v${escapeHtml(state.health.version || '2.2.1')}` : ''}" in js
    assert "${state.health ? `v${state.health.version || '2.2.1'}` : ''}" not in js


def test_explorer_epoch_progress_uses_numeric_api_values():
    js = source()

    assert "const slot = Number.isFinite(Number(epoch.slot)) ? Number(epoch.slot) : 0;" in js
    assert (
        "const blocksPerEpoch = Number.isFinite(Number(epoch.blocks_per_epoch)) "
        "&& Number(epoch.blocks_per_epoch) > 0"
    ) in js
    assert "Math.max(0, Math.min(100, (slot / blocksPerEpoch) * 100))" in js
    assert "${formatNumber(slot, 0)}/${formatNumber(blocksPerEpoch, 0)}" in js
    assert "${formatNumber(epoch.slot || 0, 0)}/${epoch.blocks_per_epoch || 144}" not in js


def test_explorer_escapes_miner_ids_in_normal_table_and_search_results():
    js = source()

    safe_pattern = (
        '<td class="mono" title="${escapeHtml(minerId)}">'
        "${escapeHtml(shortenAddress(minerId))}</td>"
    )
    assert js.count(safe_pattern) == 2
    assert "${shortenAddress(minerId)}</td>" not in js
    assert "${shortenAddress(miner.miner_id || 'unknown')}</td>" not in js

    assert "const minerId = miner.miner_id || miner.miner || 'unknown';" in js
    assert "const arch = miner.device_arch || miner.device_family || miner.hardware_type || 'Unknown';" in js
