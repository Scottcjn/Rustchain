from pathlib import Path
import json
import subprocess

JS = Path('explorer/static/js/explorer.js').read_text(encoding='utf-8')


def test_explorer_normalizes_paginated_miners_response():
    assert JS.count('function normalizeMinersResponse(') == 1
    assert "Array.isArray(payload?.miners)" in JS
    assert "Array.isArray(payload?.data)" in JS
    assert "return rows.filter(row => row && typeof row === 'object');" in JS
    assert "state.miners = normalizeMinersResponse(await fetchAPI('/api/miners'));" in JS


def test_explorer_keeps_legacy_array_response_compatible():
    assert 'Array.isArray(payload) ? payload' in JS


def test_explorer_helpers_tolerate_malformed_miner_fields():
    probe = f"""
const vm = require('vm');
const script = {json.dumps(JS)};
const context = {{
  window: {{ EXPLORER_API_BASE: 'https://example.test' }},
  document: {{
    addEventListener() {{}},
    getElementById() {{ return null; }},
    querySelectorAll() {{ return []; }},
  }},
  setInterval() {{}},
  setTimeout() {{ return 1; }},
  clearTimeout() {{}},
  AbortController: class {{ constructor() {{ this.signal = {{}}; }} abort() {{}} }},
  fetch: async () => ({{ ok: true, json: async () => ({{}}) }}),
  console: {{ error() {{}}, warn() {{}}, log() {{}} }},
}};
vm.createContext(context);
vm.runInContext(script, context);
const payload = {{ miners: [null, 'bad', {{ miner_id: {{ id: 'm' }}, device_arch: ['G4'], balance: 'NaN' }}] }};
const result = {{
  miners: vm.runInContext('normalizeMinersResponse', context)(payload),
  address: vm.runInContext('shortenAddress', context)({{ id: 'm' }}),
  tier: vm.runInContext('getArchitectureTier', context)(['G4']),
  number: vm.runInContext('formatNumber', context)('NaN', 2),
}};
console.log(JSON.stringify(result));
"""
    result = subprocess.run(
        ["node", "-e", probe],
        text=True,
        capture_output=True,
        check=True,
    )
    data = json.loads(result.stdout)

    assert data["miners"] == [{"miner_id": {"id": "m"}, "device_arch": ["G4"], "balance": "NaN"}]
    assert data["address"] == "[objec...bject]"
    assert data["tier"] == "vintage"
    assert data["number"] == "0"
