# SPDX-License-Identifier: MIT
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REALTIME_EXPLORER = ROOT / "explorer" / "realtime-explorer.html"


def test_websocket_feed_renders_event_fields_with_text_nodes():
    html = REALTIME_EXPLORER.read_text()

    assert "feed.innerHTML = feedItems.map" not in html
    assert "${item.icon}" not in html
    assert "${item.title}" not in html
    assert "${item.subtitle}" not in html
    assert "feed.replaceChildren(...items)" in html
    assert "textElement('span', 'feed-icon', item.icon)" in html
    assert "textElement('div', 'feed-title', item.title)" in html
    assert "textElement('div', null, item.subtitle)" in html


def test_epoch_notification_does_not_interpolate_websocket_payload_html():
    html = REALTIME_EXPLORER.read_text()

    assert "notification.innerHTML = `" not in html
    assert "<p>Epoch ${data.epoch}" not in html
    assert "<strong>Pot:</strong> ${data.total_rtc" not in html
    assert "<strong>Miners:</strong> ${data.miners" not in html
    assert "document.createTextNode(` ${data.total_rtc || 0} RTC`)" in html
    assert "document.createTextNode(` ${data.miners || 0}`)" in html


def test_api_numeric_fields_are_formatted_safely():
    html = REALTIME_EXPLORER.read_text()

    assert "function safeNumber(value, fallback = 0)" in html
    assert "function formatNumber(value, decimals)" in html
    assert "${esc(formatNumber(miner.earnings || miner.total_earned, 2))} RTC" in html
    assert (
        "document.getElementById('epoch-pot').textContent = "
        "formatNumber(epoch.pot || epoch.pot_rtc, 2);"
    ) in html
    assert "${esc(formatNumber(block.reward, 4))} RTC" in html
    assert "(miner.earnings || miner.total_earned || 0).toFixed(2)" not in html
    assert "(epoch.pot || epoch.pot_rtc || 0).toFixed(2)" not in html
    assert "(block.reward || 0).toFixed(4)" not in html
