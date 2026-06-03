# SPDX-License-Identifier: MIT
"""Regression checks for realtime explorer miner response normalization."""

from pathlib import Path


REALTIME_JS = (
    Path(__file__).resolve().parents[1] / "explorer" / "static" / "js" / "realtime.js"
)


def source():
    return REALTIME_JS.read_text(encoding="utf-8")


def test_polling_client_normalizes_paginated_miners_response():
    js = source()

    assert "normalizeMinersResponse(response)" in js
    assert "Array.isArray(response?.miners)" in js
    assert "return response.miners;" in js
    assert "const miners = this.normalizeMinersResponse(minersResponse);" in js
    assert "miners: miners.length" in js


def test_polling_client_does_not_use_raw_miners_response_for_metrics():
    js = source()

    assert "this.fetchJSON('/api/miners')," in js
    assert "const [blocks, transactions, minersResponse, epoch]" in js
    assert "const [blocks, transactions, miners, epoch]" not in js
