# SPDX-License-Identifier: MIT

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OTC_HTML = ROOT / "otc-bridge" / "static" / "index.html"


def test_otc_bridge_normalizes_response_arrays_before_rendering():
    html = OTC_HTML.read_text(encoding="utf-8")

    assert "const asks = Array.isArray(data.asks) ? data.asks : [];" in html
    assert "const bids = Array.isArray(data.bids) ? data.bids : [];" in html
    assert "const orders = Array.isArray(data.orders) ? data.orders : [];" in html
    assert "const trades = Array.isArray(data.trades) ? data.trades : [];" in html


def test_otc_bridge_formats_api_numbers_through_safe_helpers():
    html = OTC_HTML.read_text(encoding="utf-8")

    assert "function safeOptionalNumber(value)" in html
    assert "const spread = safeOptionalNumber(data.spread);" in html
    assert "const lastPrice = safeOptionalNumber(data.last_price);" in html
    assert "const total = safeNumber(data.total, orders.length);" in html
    assert "data.spread.toFixed" not in html
    assert "data.last_price.toFixed" not in html
    assert "data.volume_24h_rtc.toFixed" not in html
    assert "s.last_price.toFixed" not in html
