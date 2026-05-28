# SPDX-License-Identifier: MIT
import json
import subprocess
import textwrap
from pathlib import Path


PAGE = Path(__file__).resolve().parents[1] / "static" / "status" / "index.html"


def run_status_dashboard_probe(payload, assertions: str, *, ok: bool = True, status: int = 200) -> None:
    script = f"""
    const fs = require('fs');
    const vm = require('vm');
    const html = fs.readFileSync({json.dumps(str(PAGE))}, 'utf8');
    const source = html.match(/<script>([\\s\\S]*?)<\\/script>/)[1];

    function makeElement(tagName) {{
        return {{
            tagName,
            children: [],
            className: '',
            style: {{}},
            _innerHTML: '',
            _innerText: '',
            _textContent: '',
            appendChild(child) {{
                this.children.push(child);
            }},
            set innerHTML(value) {{
                this._innerHTML = String(value);
                this.children = [];
            }},
            get innerHTML() {{
                return this._innerHTML;
            }},
            set innerText(value) {{
                this._innerText = String(value);
            }},
            get innerText() {{
                return this._innerText;
            }},
            set textContent(value) {{
                this._textContent = String(value);
            }},
            get textContent() {{
                return this._textContent;
            }}
        }};
    }}

    const elements = {{
        nodeGrid: makeElement('div'),
        lastUpdate: makeElement('div'),
        sysTime: makeElement('span')
    }};
    const context = {{
        document: {{
            getElementById: id => elements[id],
            createElement: makeElement
        }},
        fetch: async () => ({{
            ok: {json.dumps(ok)},
            status: {status},
            json: async () => ({json.dumps(payload)})
        }}),
        console: {{ error() {{}} }},
        Date,
        setInterval: () => 1
    }};

    vm.createContext(context);
    vm.runInContext(source, context);
    context.updateStatus().then(() => {{
        const nodeGrid = elements.nodeGrid;
        const lastUpdate = elements.lastUpdate;
        {assertions}
    }}).catch(error => {{
        console.error(error);
        process.exit(1);
    }});
    """
    subprocess.run(["node", "-e", textwrap.dedent(script)], check=True)


def test_status_dashboard_defines_render_safety_helpers():
    html = PAGE.read_text(encoding="utf-8")

    assert "function escapeHtml(value)" in html
    assert "function safeStatus(value)" in html
    assert "function safeNumber(value, fallback = '--')" in html
    assert "function safeArray(value)" in html
    assert "function safeObject(value)" in html
    assert "function isValidNode(value)" in html
    assert "function formatTimestamp(value)" in html
    assert "function renderUnavailable(grid)" in html


def test_status_dashboard_escapes_node_status_fields_before_inner_html():
    html = PAGE.read_text(encoding="utf-8")

    safe_patterns = [
        "const status = safeStatus(node.status);",
        "const statusColor = status === 'up' ? 'var(--green)' : 'var(--red)';",
        "return found ? safeStatus(found.status) === 'up' : false;",
        'class="status-dot ${status}"',
        "${escapeHtml(node.name)}",
        '<div class="location">${escapeHtml(node.location)}</div>',
        "${escapeHtml(status.toUpperCase())}",
        "${escapeHtml(safeNumber(node.latency_ms))}ms",
        "${escapeHtml(node.version || 'unknown')}",
        "${escapeHtml(safeNumber(node.epoch))}",
        "${escapeHtml(safeNumber(node.miners, 0))}",
    ]

    for pattern in safe_patterns:
        assert pattern in html

    unsafe_patterns = [
        "${node.name}",
        "${node.location}",
        "${node.status.toUpperCase()}",
        "${node.latency_ms || '--'}ms",
        "${node.version || 'unknown'}",
        "${node.epoch || '--'}",
        "${node.miners || 0}",
        "found.status === 'up'",
    ]

    for pattern in unsafe_patterns:
        assert pattern not in html


def test_status_dashboard_handles_empty_or_malformed_history_payloads():
    run_status_dashboard_probe(
        {"not": "a history array"},
        """
        if (nodeGrid.children.length !== 1) {
            throw new Error('expected one empty-state card');
        }
        if (nodeGrid.children[0].textContent !== 'No node status data available') {
            throw new Error('missing empty-state message');
        }
        if (lastUpdate.innerText !== 'LAST_UPDATE: unavailable') {
            throw new Error('missing unavailable timestamp');
        }
        """,
    )


def test_status_dashboard_handles_malformed_history_rows():
    run_status_dashboard_probe(
        [
            {"time": "2026-05-20T00:00:00Z", "nodes": None},
            {
                "time": "bad",
                "nodes": [
                    None,
                    ["bad"],
                    {
                        "name": "<img src=x onerror=alert(1)>",
                        "url": "https://node.example/health",
                        "location": "Lab",
                        "status": "up",
                    }
                ],
            },
        ],
        """
        if (nodeGrid.children.length !== 1) {
            throw new Error('expected one rendered node card');
        }
        if (!nodeGrid.children[0].innerHTML.includes('&lt;img src=x onerror=alert(1)&gt;')) {
            throw new Error('node name was not escaped');
        }
        if (!nodeGrid.children[0].innerHTML.includes('status-dot up')) {
            throw new Error('safe status class was not rendered');
        }
        if (lastUpdate.innerText !== 'LAST_UPDATE: unavailable') {
            throw new Error('invalid timestamp should render unavailable');
        }
        """,
    )


def test_status_dashboard_renders_empty_state_for_fetch_failures():
    run_status_dashboard_probe(
        {},
        """
        if (nodeGrid.children.length !== 1) {
            throw new Error('expected one empty-state card');
        }
        if (nodeGrid.children[0].textContent !== 'No node status data available') {
            throw new Error('missing empty-state message');
        }
        if (lastUpdate.innerText !== 'LAST_UPDATE: unavailable') {
            throw new Error('missing unavailable timestamp');
        }
        """,
        ok=False,
        status=404,
    )
