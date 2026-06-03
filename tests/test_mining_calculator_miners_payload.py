# SPDX-License-Identifier: MIT
"""Source checks for mining calculator miner payload handling."""

from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / "mining-calculator" / "index.html"


def test_mining_calculator_normalizes_current_miners_envelope():
    html = SOURCE.read_text()

    assert "function normalizeNetworkPayload(payload)" in html
    assert "Array.isArray(payload?.miners)" in html
    assert "Number(payload?.pagination?.total)" in html
    assert "return normalizeNetworkPayload(payload);" in html
    assert "activeMiners = networkData.total;" in html
    assert "const miners = networkData?.miners || [];" in html
    assert "if (miners && miners.length > 0)" not in html
