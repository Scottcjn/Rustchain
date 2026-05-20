# SPDX-License-Identifier: MIT

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OTC_HTML = ROOT / "otc-bridge" / "static" / "index.html"


def test_otc_bridge_normalizes_response_arrays_before_rendering():
    html = OTC_HTML.read_text(encoding="utf-8")

    assert "const asks = Array.isArray(data.asks) ? data.asks : [];" in html
    assert "const bids = Array.isArray(data.bids) ? data.bids : [];" in html
    assert "const rawOrders = Array.isArray(data.orders) ? data.orders : [];" in html
    assert "const orders = rawOrders.filter(o => o && typeof o === 'object' && String(o.order_id ?? '').trim() !== '');" in html
    assert "const trades = Array.isArray(data.trades) ? data.trades : [];" in html
    assert "const order = o;" in html
    assert "${escapeHtml(order.maker_wallet)}" in html
    assert "${escapeHtml(o.maker_wallet)}" not in html


def test_otc_bridge_rejects_malformed_open_order_rows():
    html = OTC_HTML.read_text(encoding="utf-8")

    assert "openOrdersById.set(orderId, order);" in html
    assert "data-order-id=\"${escapeHtml(orderId)}\"" in html
    assert "const orders = rawOrders.filter(o => o && typeof o === 'object' && String(o.order_id ?? '').trim() !== '');" in html
    assert "const orderId = String(order.order_id ?? '');" in html


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
