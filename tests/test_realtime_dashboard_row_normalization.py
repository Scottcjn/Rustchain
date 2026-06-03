# SPDX-License-Identifier: MIT

from pathlib import Path
import json
import subprocess


DASHBOARD_JS = Path(__file__).resolve().parents[1] / "explorer" / "static" / "js" / "dashboard.js"


def source() -> str:
    return DASHBOARD_JS.read_text(encoding="utf-8")


def test_dashboard_filters_malformed_realtime_rows():
    js = source()

    assert "normalizeRows(payload)" in js
    assert "this.state.blocks = this.normalizeRows(state.blocks);" in js
    assert "this.state.transactions = this.normalizeRows(state.transactions);" in js
    assert "this.state.miners = this.normalizeRows(state.miners);" in js
    assert "if (!state || typeof state !== 'object') return;" in js
    assert "if (!block || typeof block !== 'object') return;" in js
    assert "if (!tx || typeof tx !== 'object') return;" in js


def test_dashboard_helpers_coerce_malformed_field_values():
    js = source()

    assert "const value = String(hash ?? '');" in js
    assert "const value = String(addr ?? '');" in js
    assert "if (!Number.isFinite(value)) return '0';" in js


def test_dashboard_vm_handles_malformed_realtime_payloads():
    js = source()
    probe = f"""
const vm = require('vm');
const script = {json.dumps(js)};
const context = {{
  window: {{ location: {{ origin: 'https://example.test', host: 'example.test' }} }},
  document: {{
    addEventListener() {{}},
    getElementById() {{ return null; }},
    body: {{ classList: {{ toggle() {{}}, contains() {{ return false; }} }} }},
  }},
  localStorage: {{ setItem() {{}} }},
  navigator: {{ onLine: true }},
  WebSocket: function() {{}},
  setInterval() {{ return 1; }},
  clearInterval() {{}},
  setTimeout(fn) {{ return 1; }},
  console: {{ log() {{}}, error() {{}} }},
}};
vm.createContext(context);
vm.runInContext(script, context);
const result = vm.runInContext(`
  const app = Object.create(DashboardApp.prototype);
  app.state = {{
    blocks: [],
    transactions: [],
    miners: [],
    epoch: {{}},
    health: {{}},
    metrics: {{ blocksReceived: 0, transactionsReceived: 0, updatesReceived: 0 }},
    lastUpdate: null,
  }};
  app.charts = {{}};
  app.updateAllDisplays = function() {{}};
  app.updateBlocksDisplay = function() {{}};
  app.updateBlocksChart = function() {{}};
  app.updateTransactionsDisplay = function() {{}};
  app.updateTransactionsChart = function() {{}};
  app.updateMinersDisplay = function() {{}};
  app.updateHardwareDistribution = function() {{}};
  app.updateMinersChart = function() {{}};
  app.updateMetricsDisplay = function() {{}};
  app.updateLastUpdateTime = function() {{ this.state.lastUpdate = 1; }};
  app.highlightNewBlock = function() {{}};

  app.onBlock(null);
  app.onTransaction('bad');
  app.updateState(null);
  app.updateState({{
    blocks: [null, 'bad', {{ hash: {{ id: 'h' }}, height: 'nan' }}],
    transactions: [null, {{ from: {{ id: 'from' }}, to: ['to'], amount: 'NaN' }}],
    miners: [undefined, {{ miner_id: {{ id: 'm' }}, device_arch: ['G4'], multiplier: 'NaN' }}],
  }});
  JSON.stringify({{
    blocks: app.state.blocks,
    transactions: app.state.transactions,
    miners: app.state.miners,
    hash: app.shortenHash({{ id: 'h' }}),
    address: app.shortenAddress({{ id: 'm' }}),
    number: app.formatNumber('NaN', 2),
    tier: app.getArchitectureTier(['G4']),
  }});
`, context);
console.log(result);
"""
    result = subprocess.run(
        ["node", "-e", probe],
        text=True,
        capture_output=True,
        check=True,
    )
    data = json.loads(result.stdout)

    assert data["blocks"] == [{"hash": {"id": "h"}, "height": "nan"}]
    assert data["transactions"] == [{"from": {"id": "from"}, "to": ["to"], "amount": "NaN"}]
    assert data["miners"] == [{"miner_id": {"id": "m"}, "device_arch": ["G4"], "multiplier": "NaN"}]
    assert data["hash"] == "[object Object]"
    assert data["address"] == "[objec...bject]"
    assert data["number"] == "0"
    assert data["tier"] == "vintage"
