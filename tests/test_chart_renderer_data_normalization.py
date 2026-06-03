# SPDX-License-Identifier: MIT
import json
import subprocess
import textwrap
from pathlib import Path


CHARTS = Path(__file__).resolve().parents[1] / "explorer" / "static" / "js" / "charts.js"


def run_chart_probe(body: str) -> None:
    script = f"""
    const fs = require('fs');
    const vm = require('vm');
    const source = fs.readFileSync({json.dumps(str(CHARTS))}, 'utf8');

    const noop = () => undefined;
    const ctx = new Proxy({{}}, {{
        get(target, prop) {{
            if (prop === 'createLinearGradient') {{
                return () => ({{ addColorStop: noop }});
            }}
            return target[prop] || noop;
        }},
        set(target, prop, value) {{
            target[prop] = value;
            return true;
        }}
    }});
    const canvas = {{
        style: {{}},
        getContext: () => ctx
    }};
    global.window = global;
    global.document = {{
        getElementById: () => ({{
            clientWidth: 400,
            innerHTML: '',
            appendChild: noop,
            removeChild: noop
        }}),
        createElement: () => canvas
    }};
    global.ResizeObserver = undefined;
    global.performance = {{ now: () => 0 }};
    global.requestAnimationFrame = (callback) => {{
        callback(300);
        return 1;
    }};
    global.cancelAnimationFrame = noop;

    vm.runInThisContext(source);

    {body}
    """
    subprocess.run(["node", "-e", textwrap.dedent(script)], check=True)


def test_chart_renderer_normalizes_update_payloads_to_arrays():
    source = CHARTS.read_text(encoding="utf-8")

    assert "asArray(data)" in source
    assert "return Array.isArray(data) ? data : [];" in source
    assert "this.targetData = this.asArray(newData);" in source
    assert "this.data = this.targetData;" in source
    assert "const startData = this.asArray(this.data).length > 0 ? this.asArray(this.data) : this.targetData;" in source
    assert "this.targetData = newData;" not in source
    assert "this.data = newData;" not in source


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

    assert "isSliceObject(item)" in source
    assert "return item && typeof item === 'object' && !Array.isArray(item);" in source
    assert "getSliceValue(item)" in source
    assert "if (!this.isSliceObject(item)) return 0;" in source
    assert "return Math.max(0, this.numericValue(item.value));" in source
    assert "getSliceLabel(item)" in source
    assert "this.ctx.fillText(this.getSliceLabel(item), labelX, labelY);" in source
    assert "const total = slices.reduce((sum, item) => sum + this.getSliceValue(item), 0);" in source
    assert "if (total <= 0) return;" in source
    assert "const value = this.getSliceValue(item);" in source
    assert "this.ctx.fillText(item.label || '', labelX, labelY);" not in source
    assert "const total = this.data.reduce((sum, item) => sum + (item.value || 0), 0);" not in source
    assert "const value = item.value || 0;" not in source


def test_non_animated_update_stores_normalized_array():
    run_chart_probe(
        """
        const chart = new ChartRenderer('chart', {
            animation: false,
            showGrid: false,
            showLegend: false
        });
        chart.update({ not: 'array' });

        if (!Array.isArray(chart.targetData) || chart.targetData.length !== 0) {
            throw new Error('targetData was not normalized');
        }
        if (!Array.isArray(chart.data) || chart.data.length !== 0) {
            throw new Error('data was not normalized for non-animated update');
        }
        """
    )


def test_malformed_pie_slices_do_not_throw():
    run_chart_probe(
        """
        const chart = new ChartRenderer('chart', {
            type: 'pie',
            animation: false,
            showGrid: false,
            showLegend: true
        });

        chart.update([{ label: 'valid', value: 1 }, null]);
        chart.update([null, { label: 'valid', value: 1 }]);
        """
    )
