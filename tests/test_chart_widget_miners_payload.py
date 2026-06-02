# SPDX-License-Identifier: MIT
"""Source checks for the chart widget miner payload handling."""

from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / "dashboards" / "chart-widget" / "chart-widget.html"


def test_chart_widget_normalizes_current_miners_envelope():
    html = SOURCE.read_text()

    assert "function normalizeMinersPayload(payload)" in html
    assert "Array.isArray(payload?.miners)" in html
    assert "Number(payload?.pagination?.total)" in html
    assert "const { total: activeMiners } = normalizeMinersPayload(minersPayload);" in html
    assert "`${activeMiners} attesting now`" in html
    assert "`${miners.length} attesting now`" not in html
