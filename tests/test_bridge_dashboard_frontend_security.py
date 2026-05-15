# SPDX-License-Identifier: MIT
from pathlib import Path


def test_bridge_monitor_escapes_transaction_fields_before_inner_html():
    page = Path(__file__).resolve().parents[1] / "static" / "bridge" / "index.html"
    html = page.read_text(encoding="utf-8")

    assert "function escapeHtml(value)" in html
    assert "function safeClassToken(value, allowed, fallback)" in html
    assert "function safeNumber(value, fallback = 0)" in html

    safe_patterns = [
        "const lockId = escapeHtml(String(tx.lock_id ?? '').substring(0, 12));",
        "${escapeHtml(tx.sender_wallet)}",
        "${escapeHtml(safeNumber(tx.amount_rtc))}",
        "${escapeHtml(targetChain.toUpperCase())}",
        'class="state-tag ${state}"',
        "${escapeHtml(state.toUpperCase())}",
    ]

    for pattern in safe_patterns:
        assert pattern in html

    unsafe_patterns = [
        "${tx.lock_id.substring(0,12)}",
        "${tx.sender_wallet}",
        "${tx.amount_rtc}",
        "${tx.target_chain.toUpperCase()}",
        'class="state-tag ${tx.state}"',
        "${tx.state.toUpperCase()}",
    ]

    for pattern in unsafe_patterns:
        assert pattern not in html


def test_bridge_dashboard_escapes_transaction_fields_before_inner_html():
    page = Path(__file__).resolve().parents[1] / "static" / "bridge" / "dashboard.html"
    html = page.read_text(encoding="utf-8")

    assert "function escapeHtml(value)" in html
    assert "function safeClassToken(value, allowed, fallback)" in html

    safe_patterns = [
        "${escapeHtml(String(tx.lock_id ?? '').substring(0, 16))}",
        'class="tx-type ${safeClassToken(tx.type, [\'wrap\', \'unwrap\'], \'wrap\')}"',
        "${escapeHtml(safeClassToken(tx.type, ['wrap', 'unwrap'], 'wrap').toUpperCase())}",
        "${escapeHtml(tx.sender_wallet)}",
        "${escapeHtml(formatNumber(tx.amount_rtc))}",
        'class="chain-badge ${safeClassToken(tx.target_chain, [\'solana\', \'base\'], \'solana\')}"',
        "${escapeHtml(safeClassToken(tx.target_chain, ['solana', 'base'], 'solana').toUpperCase())}",
        'class="tx-state ${safeClassToken(tx.state, [\'complete\', \'pending\', \'confirmed\', \'requested\'], \'pending\')}"',
        "${escapeHtml(safeClassToken(tx.state, ['complete', 'pending', 'confirmed', 'requested'], 'pending').toUpperCase())}",
    ]

    for pattern in safe_patterns:
        assert pattern in html

    unsafe_patterns = [
        "${tx.lock_id.substring(0, 16)}",
        'class="tx-type ${tx.type}"',
        "${tx.type.toUpperCase()}",
        "${tx.sender_wallet}",
        "${formatNumber(tx.amount_rtc)}",
        "${tx.type === 'wrap' ? 'RTC' : 'wRTC'}",
        'class="chain-badge ${tx.target_chain}"',
        "${tx.target_chain.toUpperCase()}",
        'class="tx-state ${tx.state}"',
        "${tx.state.toUpperCase()}",
    ]

    for pattern in unsafe_patterns:
        assert pattern not in html
