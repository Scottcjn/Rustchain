# SPDX-License-Identifier: MIT
from pathlib import Path


CHARTS = Path(__file__).resolve().parents[1] / "explorer" / "static" / "js" / "charts.js"


def test_chart_renderer_normalizes_update_payloads_to_arrays():
    source = CHARTS.read_text(encoding="utf-8")

    assert "asArray(data)" in source
    assert "return Array.isArray(data) ? data : [];" in source
    assert "this.targetData = this.asArray(newData);" in source
    assert "const startData = this.asArray(this.data).length > 0 ? this.asArray(this.data) : this.targetData;" in source
    assert "this.targetData = newData;" not in source


def test_chart_renderer_coerces_numeric_series_before_drawing():
    source = CHARTS.read_text(encoding="utf-8")

    safe_patterns = [
        "numericValue(value, fallback = 0)",
        "return Number.isFinite(number) ? number : fallback;",
        "getNumericData()",
        "const data = this.getNumericData();",
        "const maxValue = Math.max(...data);",
        "data.forEach((value, index) => {",
        "value.toFixed(1)",
    ]

    for pattern in safe_patterns:
        assert pattern in source

    unsafe_patterns = [
        "Math.max(...this.data.map(d => typeof d === 'number' ? d : 0))",
        "Math.min(...this.data.map(d => typeof d === 'number' ? d : 0))",
        "this.data.forEach((value, index) => {",
        "const barWidth = (chartWidth / this.data.length) * 0.8;",
    ]

    for pattern in unsafe_patterns:
        assert pattern not in source


def test_chart_renderer_skips_zero_total_pie_and_doughnut_charts():
    source = CHARTS.read_text(encoding="utf-8")

    assert "getSliceValue(item)" in source
    assert "return Math.max(0, this.numericValue(item && item.value));" in source
    assert "const total = slices.reduce((sum, item) => sum + this.getSliceValue(item), 0);" in source
    assert "if (total <= 0) return;" in source
    assert "const value = this.getSliceValue(item);" in source
    assert "const total = this.data.reduce((sum, item) => sum + (item.value || 0), 0);" not in source
    assert "const value = item.value || 0;" not in source
