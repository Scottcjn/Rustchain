# SPDX-License-Identifier: MIT
from pathlib import Path


DASHBOARD = Path(__file__).resolve().parents[1] / "explorer" / "templates" / "dashboard.html"


def test_dashboard_refresh_normalizes_api_payload_before_rendering():
    html = DASHBOARD.read_text(encoding="utf-8")

    assert "function asObject(value)" in html
    assert "function asArray(value)" in html
    assert "function displayText(value, fallback = '--')" in html
    assert "const payload = asObject(data);" in html
    assert "updateNetworkStats(payload.network_stats);" in html
    assert "updateRecentBlocks(payload.recent_blocks);" in html
    assert "updateMiners(payload.miners);" in html
    assert "updateNetworkStats(data.network_stats);" not in html
    assert "updateRecentBlocks(data.recent_blocks);" not in html
    assert "updateMiners(data.miners);" not in html


def test_dashboard_tables_guard_missing_or_malformed_rows():
    html = DASHBOARD.read_text(encoding="utf-8")

    safe_patterns = [
        "const safeStats = asObject(stats);",
        "textContent = displayText(safeStats.block_height);",
        "const blockList = asArray(blocks);",
        "if (blockList.length === 0) {",
        "No recent blocks",
        "tbody.innerHTML = blockList.map(block => `",
        "const minerList = asArray(miners);",
        "if (minerList.length === 0) {",
        "No miners found",
        "tbody.innerHTML = minerList.map(miner => {",
    ]

    for pattern in safe_patterns:
        assert pattern in html

    unsafe_patterns = [
        "textContent = stats.block_height;",
        "tbody.innerHTML = blocks.map(block => `",
        "tbody.innerHTML = miners.map(miner => {",
    ]

    for pattern in unsafe_patterns:
        assert pattern not in html
