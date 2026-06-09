# SPDX-License-Identifier: MIT
import json
import subprocess
import textwrap
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC_DASHBOARD = ROOT / "static" / "bridge" / "dashboard.html"
TOOL_DASHBOARD_JS = ROOT / "tools" / "wrtc-bridge-dashboard" / "bridge_dashboard.js"
DEX_URL = (
    "https://api.dexscreener.com/latest/dex/tokens/"
    "12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X"
)


def run_static_dashboard_probe(responses, assertions: str) -> None:
    script = f"""
    const fs = require('fs');
    const vm = require('vm');

    const html = fs.readFileSync({json.dumps(str(STATIC_DASHBOARD))}, 'utf8');
    const source = html.match(/<script>([\\s\\S]*?)<\\/script>/)[1];

    function makeElement(id) {{
        return {{
            id,
            children: [],
            className: '',
            style: {{}},
            _text: '',
            _html: '',
            appendChild(child) {{
                this.children.push(child);
            }},
            getContext() {{
                return {{}};
            }},
            set textContent(value) {{
                this._text = String(value);
            }},
            get textContent() {{
                return this._text;
            }},
            set innerText(value) {{
                this._text = String(value);
            }},
            get innerText() {{
                return this._text;
            }},
            set innerHTML(value) {{
                this._html = String(value);
                this.children = [];
            }},
            get innerHTML() {{
                return this._html;
            }},
        }};
    }}

    const elementIds = [
        'lockedRtc', 'circulatingWrtc', 'wrapVolume', 'unwrapVolume',
        'currentPrice', 'priceSol', 'change24h', 'liquidity', 'volume24h',
        'marketCap', 'priceChangeLarge', 'priceChart',
        'totalFees', 'wrapFees', 'unwrapFees', 'avgFee',
        'rustchainStatus', 'rustchainDetail', 'solanaStatus', 'solanaDetail',
        'bridgeStatus', 'bridgeDetail', 'raydiumStatus', 'raydiumDetail',
        'txBody', 'lastUpdate'
    ];
    const elements = Object.fromEntries(elementIds.map(id => [id, makeElement(id)]));
    const responses = {json.dumps(responses)};
    const fetchLog = [];

    const context = {{
        document: {{
            getElementById(id) {{
                if (!elements[id]) elements[id] = makeElement(id);
                return elements[id];
            }},
            querySelectorAll() {{
                return [];
            }},
            addEventListener() {{}},
        }},
        fetch: async url => {{
            const key = String(url);
            fetchLog.push(key);
            const res = responses[key];
            if (!res) throw new Error(`unexpected fetch: ${{key}}`);
            return {{
                ok: res.ok !== false,
                status: res.status || (res.ok === false ? 500 : 200),
                headers: {{ get: () => res.contentType || 'application/json' }},
                json: async () => {{
                    if (res.jsonThrows) throw new Error('invalid json');
                    return res.body;
                }},
            }};
        }},
        console: {{ log() {{}}, error() {{}} }},
        Chart: function() {{ this.data = {{ labels: [], datasets: [{{ data: [] }}] }}; this.update = () => {{}}; }},
        Date,
        Intl,
        Promise,
        setInterval: () => 1,
    }};

    vm.createContext(context);
    vm.runInContext(source, context);
    vm.runInContext('refreshAll()', context).then(() => {{
        {assertions}
    }}).catch(error => {{
        console.error(error);
        process.exit(1);
    }});
    """
    subprocess.run(["node", "-e", textwrap.dedent(script)], check=True, cwd=ROOT)


def run_tool_dashboard_probe(responses, assertions: str) -> None:
    script = f"""
    const fs = require('fs');
    const vm = require('vm');

    const source = fs.readFileSync({json.dumps(str(TOOL_DASHBOARD_JS))}, 'utf8');

    function makeElement() {{
        return {{
            style: {{}},
            className: '',
            textContent: '',
            innerHTML: '',
            setAttribute() {{}},
        }};
    }}

    const elements = {{}};
    const responses = {json.dumps(responses)};
    const fetchLog = [];
    const context = {{
        document: {{
            getElementById(id) {{
                if (!elements[id]) elements[id] = makeElement();
                return elements[id];
            }},
        }},
        fetch: async (url) => {{
            const key = String(url);
            fetchLog.push(key);
            const res = responses[key] || {{ ok: false, status: 404, body: {{}} }};
            return {{
                ok: res.ok !== false,
                status: res.status || (res.ok === false ? 500 : 200),
                headers: {{ get: () => res.contentType || 'application/json' }},
                json: async () => {{
                    if (res.jsonThrows) throw new Error('invalid json');
                    return res.body;
                }},
            }};
        }},
        console: {{ log() {{}}, error() {{}} }},
        Date,
        Math,
        Array,
        Number,
        parseFloat,
        setInterval: () => 1,
    }};

    vm.createContext(context);
    vm.runInContext(source, context);
    fetchLog.length = 0;
    vm.runInContext('fetchBridgeTransactions()', context).then(result => {{
        {assertions}
    }}).catch(error => {{
        console.error(error);
        process.exit(1);
    }});
    """
    subprocess.run(["node", "-e", textwrap.dedent(script)], check=True, cwd=ROOT)


def test_static_bridge_dashboard_uses_live_stats_and_ledger_payloads():
    run_static_dashboard_probe(
        {
            DEX_URL: {
                "body": {
                    "pairs": [
                        {
                            "dexId": "raydium",
                            "priceUsd": "2.5",
                            "priceNative": "0.01",
                            "priceChange": {"h24": "1.25"},
                            "liquidity": {"usd": "1000"},
                            "volume": {"h24": "250"},
                        }
                    ]
                }
            },
            "https://rustchain.org/api/bridge/stats": {
                "body": {
                    "total_locked_rtc": 42,
                    "circulating_wrtc": 41,
                    "wrap_volume": 100,
                    "unwrap_volume": 25,
                    "total_fees": 1.5,
                    "wrap_fees": 1.0,
                    "unwrap_fees": 0.5,
                }
            },
            "https://rustchain.org/api/bridge/ledger?limit=50": {
                "body": {
                    "locks": [
                        {
                            "lock_id": "live_lock_123456789",
                            "sender_wallet": "live_sender",
                            "amount_rtc": 7,
                            "target_chain": "solana",
                            "state": "complete",
                            "timestamp": 1700000000,
                        }
                    ]
                }
            },
            "https://rustchain.org/epoch": {"body": {"epoch": 188, "slot": 27108}},
        },
        """
        if (elements.lockedRtc.textContent !== '42 RTC') throw new Error(elements.lockedRtc.textContent);
        if (elements.circulatingWrtc.textContent !== '41 wRTC') throw new Error(elements.circulatingWrtc.textContent);
        if (elements.totalFees.textContent !== '1.5 RTC') throw new Error(elements.totalFees.textContent);
        if (!elements.txBody.innerHTML.includes('live_lock_123456')) throw new Error(elements.txBody.innerHTML);
        if (elements.txBody.innerHTML.includes('lock_a1b2')) throw new Error('mock transaction rendered');
        """,
    )


def test_static_bridge_dashboard_falls_back_to_public_wallet_history_envelope():
    run_static_dashboard_probe(
        {
            DEX_URL: {"body": {"pairs": []}},
            "https://rustchain.org/api/bridge/stats": {
                "ok": False,
                "status": 404,
                "contentType": "text/html",
                "jsonThrows": True,
            },
            "https://rustchain.org/api/bridge/ledger?limit=50": {
                "ok": False,
                "status": 404,
                "contentType": "text/html",
                "jsonThrows": True,
            },
            "https://rustchain.org/wallet/balance?miner_id=bridge-escrow": {
                "body": {"amount_rtc": 3.25, "miner_id": "bridge-escrow"}
            },
            "https://rustchain.org/wallet/history?miner_id=bridge-escrow&limit=50": {
                "body": {
                    "ok": True,
                    "transactions": [
                        {
                            "tx_hash": "wallet_history_tx_1",
                            "from_miner": "bridge-escrow",
                            "to_miner": "alice",
                            "amount_rtc": 3.25,
                            "status": "confirmed",
                            "created_at": 1700000000,
                        }
                    ],
                }
            },
            "https://rustchain.org/epoch": {"body": {"epoch": 188, "slot": 27108}},
        },
        """
        if (elements.lockedRtc.textContent !== '3.25 RTC') throw new Error(elements.lockedRtc.textContent);
        if (!elements.txBody.innerHTML.includes('wallet_history_t')) throw new Error(elements.txBody.innerHTML);
        if (elements.txBody.innerHTML.includes('lock_a1b2')) throw new Error('mock transaction rendered');
        if (!fetchLog.includes('https://rustchain.org/wallet/history?miner_id=bridge-escrow&limit=50')) {
            throw new Error('wallet history fallback was not queried');
        }
        """,
    )


def test_light_bridge_dashboard_reads_wallet_history_envelope_without_stale_first_call():
    run_tool_dashboard_probe(
        {
            "https://rustchain.org/wallet/history?miner_id=bridge-escrow&limit=20": {
                "body": {
                    "ok": True,
                    "transactions": [
                        {
                            "tx_hash": "wallet_history_tx_2",
                            "from_miner": "bridge-escrow",
                            "to_miner": "alice",
                            "amount_rtc": 4.5,
                            "status": "confirmed",
                            "created_at": 1700000000,
                        }
                    ],
                }
            }
        },
        """
        if (fetchLog[0] !== 'https://rustchain.org/wallet/history?miner_id=bridge-escrow&limit=20') {
            throw new Error(`stale endpoint called first: ${fetchLog[0]}`);
        }
        if (!Array.isArray(result) || result.length !== 1) throw new Error(JSON.stringify(result));
        if (result[0].tx !== 'wallet_history_tx_2') throw new Error(JSON.stringify(result[0]));
        if (result[0].amount !== 4.5) throw new Error(JSON.stringify(result[0]));
        """,
    )
