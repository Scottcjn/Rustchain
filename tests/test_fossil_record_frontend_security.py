# SPDX-License-Identifier: MIT
from pathlib import Path


FOSSIL_HTML = Path(__file__).resolve().parents[1] / "fossils" / "index.html"


def test_fossil_record_tooltip_escapes_dynamic_html_fields():
    html = FOSSIL_HTML.read_text(encoding="utf-8")

    assert "function escapeHtml(value)" in html
    assert "function finiteNumber(value, fallback = 0)" in html
    assert "const epoch = finiteNumber(d.epoch);" in html
    assert "const count = finiteNumber(d.count);" in html
    assert "const avgRtc = finiteNumber(d.avgRtc);" in html
    assert "const avgFingerprint = finiteNumber(d.avgFingerprint);" in html
    assert "const archLabel = escapeHtml(archConfig.label || d.arch || 'unknown');" in html
    assert "const sampleMiners = d.miners.slice(0, 5).map(escapeHtml);" in html
    assert "${escapeHtml(message)}" in html

    assert "${d.epoch} — ${archConfig.label}" not in html
    assert "${d.count}</span>" not in html
    assert "${d.avgRtc?.toFixed(2) || '0'} RTC" not in html
    assert "${(d.avgFingerprint * 100).toFixed(1)}%" not in html
    assert "${sampleMiners.join(', ')}</span>" in html
    assert "<strong>Error loading data:</strong> ${message}" not in html
