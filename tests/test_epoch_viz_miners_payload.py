# SPDX-License-Identifier: MIT
"""Source checks for epoch visualizer miner payload handling."""

from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / "integrations" / "epoch-viz" / "index.html"


def test_epoch_viz_normalizes_current_miners_envelope():
    html = SOURCE.read_text()

    assert "function normalizeMinersPayload(payload)" in html
    assert "Array.isArray(payload?.miners)" in html
    assert "Array.isArray(payload?.data)" in html
    assert "minersData = normalizeMinersPayload(await resp.json());" in html
    assert "minersData = await resp.json();" not in html
