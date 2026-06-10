# SPDX-License-Identifier: MIT
from pathlib import Path


HTML_PATH = Path(__file__).resolve().parents[1] / "fossils" / "index.html"


def test_fossil_tooltip_escapes_dynamic_fields_before_html_sink():
    html = HTML_PATH.read_text(encoding="utf-8")

    assert "function escapeHtml(value)" in html
    assert "function safeNumber(value, fallback = 0)" in html
    assert "const archConfig = { ...(ARCHITECTURES[d.arch] || { label: d.arch }) };" in html
    assert "d = { ...d, epoch: escapeHtml(epoch) };" in html
    assert "archConfig.label = escapeHtml(archConfig.label);" in html
    assert "const sampleMiners = d.miners.slice(0, 5).map(escapeHtml);" in html

    safe_patterns = [
        "${escapeHtml(count)}",
        "${escapeHtml(avgRtc.toFixed(2))} RTC",
        "${escapeHtml((avgFingerprint * 100).toFixed(1))}%",
        "${sampleMiners.join(', ')}",
        "<strong>Error loading data:</strong> ${escapeHtml(message)}",
    ]
    for pattern in safe_patterns:
        assert pattern in html


def test_fossil_tooltip_and_error_avoid_raw_parser_values():
    html = HTML_PATH.read_text(encoding="utf-8")

    unsafe_patterns = [
        "${d.count}</span>",
        "${d.avgRtc?.toFixed(2) || '0'} RTC",
        "${(d.avgFingerprint * 100).toFixed(1)}%",
        "const sampleMiners = d.miners.slice(0, 5);",
        "<strong>Error loading data:</strong> ${message}",
    ]
    for pattern in unsafe_patterns:
        assert pattern not in html
