import json
import subprocess
import textwrap
from pathlib import Path


SERVER = Path(__file__).resolve().parents[1] / "health-dashboard" / "server.py"


def run_health_dashboard_probe(payload, assertions):
    script = f"""
    const fs = require('fs');
    const vm = require('vm');
    const source = fs.readFileSync({json.dumps(str(SERVER))}, 'utf8');
    const template = source.match(/HTML_TEMPLATE = '''([\\s\\S]*?)'''/)[1];
    const pageScript = template.match(/<script>([\\s\\S]*?)<\\/script>/)[1];

    function makeElement(tagName) {{
        function htmlEscape(value) {{
            return String(value)
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;');
        }}
        return {{
            tagName,
            children: [],
            style: {{}},
            _innerHTML: '',
            _textContent: '',
            appendChild(child) {{ this.children.push(child); }},
            set innerHTML(value) {{ this._innerHTML = String(value); }},
            get innerHTML() {{ return this._innerHTML || htmlEscape(this._textContent); }},
            set textContent(value) {{ this._textContent = String(value); }},
            get textContent() {{ return this._textContent; }},
            getContext() {{ return {{}}; }}
        }};
    }}

    const elements = {{
        'nodes-grid': makeElement('div'),
        'incident-list': makeElement('div'),
        'map': makeElement('div'),
    }};
    const context = {{
        document: {{
            createElement: makeElement,
            getElementById: id => elements[id] || makeElement('div'),
            addEventListener() {{}}
        }},
        Chart: function() {{}},
        fetch: async () => ({{ json: async () => ({{}}) }}),
        console: {{ error() {{}}, warn() {{}}, log() {{}} }},
        Date,
        Map,
        Number,
        String,
        Array,
        setInterval() {{ return 1; }}
    }};

    vm.createContext(context);
    vm.runInContext(pageScript, context);
    const payload = {json.dumps(payload)};
    context.payload = payload;
    vm.runInContext('renderNodes(payload.nodes); renderIncidents(payload.incidents); initMap(payload.nodes);', context);
    const nodesHtml = elements['nodes-grid'].innerHTML;
    const incidentsHtml = elements['incident-list'].innerHTML;
    const mapHtml = elements['map'].innerHTML;
    {assertions}
    """
    subprocess.run(["node", "-e", textwrap.dedent(script)], check=True)


def test_health_dashboard_escapes_status_and_incident_rendering():
    payload = {
        "nodes": [
            {
                "node_id": "node1",
                "name": '<img src=x onerror=alert("node")>',
                "status": 'up" onmouseover="alert(1)',
                "response_time_ms": "12",
                "version": "<script>alert(1)</script>",
                "uptime_s": "60",
                "active_miners": '<svg onload=alert("miners")>',
                "current_epoch": "9",
                "location": '<b onclick=alert("loc")>Lab</b>',
                "error": '<img src=x onerror=alert("err")>',
            }
        ],
        "incidents": [
            {
                "node_id": "evil-node",
                "incident_type": '<img src=x onerror=alert("type")>',
                "timestamp": "2026-06-09T00:00:00Z",
                "details": '<script>alert("details")</script>',
            }
        ],
    }
    run_health_dashboard_probe(
        payload,
        """
        if (nodesHtml.includes('<script>alert(1)</script>') || nodesHtml.includes('<img src=x onerror=alert("err")>')) {
            throw new Error('node fields reached innerHTML without escaping');
        }
        if (!nodesHtml.includes('&lt;script&gt;alert(1)&lt;/script&gt;')) {
            throw new Error('escaped node version was not rendered');
        }
        if (!nodesHtml.includes('status-badge down')) {
            throw new Error('invalid node status was not normalized');
        }
        if (incidentsHtml.includes('<script>alert("details")</script>') || incidentsHtml.includes('<img src=x')) {
            throw new Error('incident fields reached innerHTML without escaping');
        }
        if (!incidentsHtml.includes('&lt;script&gt;alert("details")&lt;/script&gt;')) {
            throw new Error('escaped incident details were not rendered');
        }
        if (mapHtml.includes('onmouseover="alert(1)')) {
            throw new Error('map title accepted unescaped status attribute text');
        }
        if (!mapHtml.includes('title="Node 1 - LiquidWeb US #1: down"')) {
            throw new Error('map title did not use normalized status');
        }
        """,
    )


def test_health_dashboard_template_contains_safety_helpers():
    source = SERVER.read_text(encoding="utf-8")

    assert "function escapeHtml(value)" in source
    assert "function escapeAttr(value)" in source
    assert "function safeStatus(value)" in source
    assert "${escapeHtml(node.version || 'unknown')}" in source
    assert "${escapeHtml(node.error)}" in source
    assert "${safeNodeName}: ${safeDetails}" in source
    assert 'title="${escapeAttr(node.name)}: ${escapeAttr(status)}"' in source

    assert "${node.version}" not in source
    assert "Error: ${node.error}" not in source
    assert "${nodeName}: ${incident.details}" not in source
    assert 'title="${node.name}:' not in source
