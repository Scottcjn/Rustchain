# SPDX-License-Identifier: MIT
"""Source checks for the live stats dashboard miner count."""

from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / "dashboard" / "index.html"


def test_live_stats_dashboard_counts_current_miners_envelope():
    html = SOURCE.read_text()

    assert "function getMinerCount(payload)" in html
    assert "Number(payload?.pagination?.total)" in html
    assert "Array.isArray(payload?.miners)" in html
    assert "Array.isArray(payload?.data)" in html
    assert "getMinerCount(miners)" in html
    assert "miners.count || miners.length || '0'" not in html
