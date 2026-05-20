# SPDX-License-Identifier: MIT
import json
import subprocess
import textwrap
from pathlib import Path


PAGE = Path(__file__).resolve().parents[1] / "static" / "bridge" / "index.html"


def run_bridge_dashboard_probe(payload, assertions: str) -> None:
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
            }}
        }};
    }}

    const elements = {{
        lockedRtc: makeElement('div'),
        circulatingWrtc: makeElement('div'),
        nodeStatus: makeElement('div'),
        txBody: makeElement('tbody'),
        lastUpdate: makeElement('div')
    }};
    const context = {{
        document: {{
            getElementById: id => elements[id],
            createElement: makeElement
        }},
        fetch: async () => ({{
            ok: true,
            status: 200,
            json: async () => ({json.dumps(payload)})
        }}),
        console: {{ error() {{}} }},
        Date,
        setInterval: () => 1
    }};

    vm.createContext(context);
    vm.runInContext(source, context);
    context.refresh().then(() => {{
        const lockedRtc = elements.lockedRtc;
        const circulatingWrtc = elements.circulatingWrtc;
        const nodeStatus = elements.nodeStatus;
        const txBody = elements.txBody;
        const lastUpdate = elements.lastUpdate;
        {assertions}
    }}).catch(error => {{
        console.error(error);
        process.exit(1);
    }});
    """
    subprocess.run(["node", "-e", textwrap.dedent(script)], check=True)


def test_bridge_dashboard_defines_payload_safety_helpers():
    html = PAGE.read_text(encoding="utf-8")

    assert "function escapeHtml(value)" in html
    assert "function safeClassToken(value, allowed, fallback)" in html
    assert "function safeNumber(value, fallback = 0)" in html
    assert "function safeArray(value)" in html
    assert "function safeObject(value)" in html


def test_bridge_dashboard_handles_empty_or_malformed_payloads():
    run_bridge_dashboard_probe(
        {"not": "bridge status"},
        """
        if (lockedRtc.innerText !== '0 RTC') {
            throw new Error('locked RTC fallback did not render');
        }
        if (circulatingWrtc.innerText !== '0 wRTC') {
            throw new Error('wRTC fallback did not render');
        }
        if (nodeStatus.children.length !== 0 || txBody.children.length !== 0) {
            throw new Error('malformed arrays should render as empty lists');
        }
        if (lastUpdate.innerText !== 'LAST_SYNC: unavailable') {
            throw new Error('missing unavailable timestamp');
        }
        """,
    )


def test_bridge_dashboard_safely_renders_malformed_nodes_and_transactions():
    run_bridge_dashboard_probe(
        {
            "total_locked_rtc": "12.5",
            "circulating_wrtc": "7",
            "timestamp": "2026-05-20T00:01:00Z",
            "bridge_nodes": [
                {"name": "<img src=x onerror=alert(1)>", "status": "up"},
                None,
            ],
            "recent_transactions": [
                {
                    "lock_id": "abcdef1234567890",
                    "sender_wallet": "<script>alert(1)</script>",
                    "amount_rtc": "5",
                    "target_chain": "javascript",
                    "state": "<bad>",
                },
                None,
            ],
        },
        """
        if (nodeStatus.children.length !== 2) {
            throw new Error('expected two status pills');
        }
        if (nodeStatus.children[0].className !== 'status-pill online') {
            throw new Error('up node status did not use safe online class');
        }
        if (!nodeStatus.children[1].innerText.includes('Unknown: DOWN')) {
            throw new Error('malformed node did not render fallback text');
        }
        if (txBody.children.length !== 2) {
            throw new Error('expected two transaction rows');
        }
        if (!txBody.children[0].innerHTML.includes('&lt;script&gt;alert(1)&lt;/script&gt;')) {
            throw new Error('sender wallet was not escaped');
        }
        if (!txBody.children[0].innerHTML.includes('SOLANA')) {
            throw new Error('target chain did not fall back to safe token');
        }
        if (!txBody.children[0].innerHTML.includes('PENDING')) {
            throw new Error('state did not fall back to safe token');
        }
        """,
    )
