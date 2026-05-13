# SPDX-License-Identifier: MIT

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OTC_HTML = ROOT / "otc-bridge" / "static" / "index.html"


def test_otc_bridge_escapes_order_wallet_fields_before_rendering():
    html = OTC_HTML.read_text(encoding="utf-8")

    assert "function escapeHtml(value)" in html
    assert "${escapeHtml(o.maker_wallet)}" in html
    assert "Counterparty: ${escapeHtml(maker)}" in html


def test_otc_bridge_does_not_embed_order_data_in_inline_match_handlers():
    html = OTC_HTML.read_text(encoding="utf-8")

    assert "onclick=\"openMatch(" not in html
    assert "data-order-id=\"${escapeHtml(orderId)}\"" in html
    assert "addEventListener('click', () => openMatchFromOrder(btn.dataset.orderId))" in html
