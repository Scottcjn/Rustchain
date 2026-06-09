import json
import subprocess
import textwrap
from pathlib import Path


PAGE = Path(__file__).resolve().parents[1] / "fossils" / "index.html"


def test_fossil_record_tooltip_and_error_fields_are_escaped():
    script = f"""
    const fs = require('fs');
    const vm = require('vm');
    const html = fs.readFileSync({json.dumps(str(PAGE))}, 'utf8');
    const source = html.match(/<script>([\\s\\S]*?)<\\/script>/)[1];

    function makeElement(id) {{
        return {{
            id,
            innerHTML: '',
            textContent: '',
            style: {{}},
            clientWidth: 1200,
            appendChild() {{}},
            addEventListener() {{}},
        }};
    }}

    const elements = {{
        tooltip: makeElement('tooltip'),
        visualization: makeElement('visualization'),
        archFilter: makeElement('archFilter'),
        timeRange: makeElement('timeRange'),
        minEpoch: makeElement('minEpoch'),
        refreshBtn: makeElement('refreshBtn'),
        exportBtn: makeElement('exportBtn'),
        sampleDataBtn: makeElement('sampleDataBtn'),
    }};

    const selection = {{
        html(value) {{
            if (value !== undefined) {{
                elements[this.id].innerHTML = String(value);
                return this;
            }}
            return elements[this.id].innerHTML;
        }},
        classed() {{ return this; }},
        style() {{ return this; }},
        on() {{ return this; }},
        append() {{ return this; }},
        attr() {{ return this; }},
        text() {{ return this; }},
        value: 'all',
        node() {{ return elements[this.id]; }},
    }};

    const context = {{
        document: {{
            getElementById(id) {{ return elements[id] || makeElement(id); }},
            createElement() {{
                return {{
                    _text: '',
                    set textContent(value) {{ this._text = String(value); }},
                    get innerHTML() {{
                        return this._text
                            .replace(/&/g, '&amp;')
                            .replace(/</g, '&lt;')
                            .replace(/>/g, '&gt;');
                    }},
                    appendChild() {{}},
                    addEventListener() {{}},
                }};
            }},
            addEventListener() {{}},
        }},
        d3: {{
            select(selector) {{
                const id = selector.startsWith('#') ? selector.slice(1) : selector;
                return Object.assign(Object.create(selection), {{ id }});
            }},
        }},
        fetch: async () => ({{ ok: false }}),
        console: {{ log() {{}}, error() {{}} }},
        window: {{ innerWidth: 1200 }},
        Math,
        Number,
        String,
        Array,
    }};

    vm.createContext(context);
    vm.runInContext(source, context);
    vm.runInContext('setupTooltip();', context);

    vm.runInContext(`
        showTooltip(
            {{ pageX: 10, pageY: 20 }},
            {{
                epoch: '<img src=x onerror=alert("epoch")>',
                arch: '<svg onload=alert("arch")>',
                count: '<img src=x onerror=alert("count")>',
                avgRtc: '12.34',
                avgFingerprint: '0.7',
                miners: ['<script>alert("miner")</script>']
            }}
        );
        showError('<img src=x onerror=alert("error")>');
    `, context);

    const tooltipHtml = elements.tooltip.innerHTML;
    const errorHtml = elements.visualization.innerHTML;
    if (tooltipHtml.includes('<script>alert("miner")</script>') || tooltipHtml.includes('<img src=x')) {{
        throw new Error('tooltip rendered unescaped attacker markup');
    }}
    if (!tooltipHtml.includes('&lt;script&gt;alert("miner")&lt;/script&gt;')) {{
        throw new Error('escaped miner id was not present');
    }}
    if (errorHtml.includes('<img src=x onerror=alert("error")>')) {{
        throw new Error('error message rendered unescaped attacker markup');
    }}
    if (!errorHtml.includes('&lt;img src=x onerror=alert("error")&gt;')) {{
        throw new Error('escaped error message was not present');
    }}
    """

    subprocess.run(["node", "-e", textwrap.dedent(script)], check=True)


def test_fossil_record_template_uses_safe_tooltip_helpers():
    source = PAGE.read_text(encoding="utf-8")

    assert "function escapeHtml(value)" in source
    assert "function safeNumber(value, fallback = 0)" in source
    assert "const sampleMiners = d.miners.slice(0, 5).map(escapeHtml);" in source
    assert "${safeMessage}" in source
    assert "${sampleMiners.join(', ')}" in source

    assert "${d.avgRtc?.toFixed(2) || '0'} RTC" not in source
    assert "${(d.avgFingerprint * 100).toFixed(1)}%" not in source
    assert "const sampleMiners = d.miners.slice(0, 5);" not in source
    assert "<strong>Error loading data:</strong> ${message}" not in source
