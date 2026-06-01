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
const elements = {{}};
const element = () => ({{
  innerHTML: '',
  addEventListener() {{}},
  dataset: {{}},
}});
const context = {{
  window: {{ EXPLORER_API_BASE: 'https://example.test' }},
  document: {{
    addEventListener() {{}},
    getElementById(id) {{
      if (!elements[id]) elements[id] = element();
      return elements[id];
    }},
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
context.payload = payload;
const result = {{
  miners: vm.runInContext('normalizeMinersResponse', context)(payload),
  address: vm.runInContext('shortenAddress', context)({{ id: 'm' }}),
  tier: vm.runInContext('getArchitectureTier', context)(['G4']),
  number: vm.runInContext('formatNumber', context)('NaN', 2),
}};
vm.runInContext('state.miners = normalizeMinersResponse(payload); state.searchQuery = "g4"; renderSearchResults();', context);
result.searchHtml = elements['search-results'].innerHTML;
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
    assert "Search Results: 1 found" in data["searchHtml"]


def test_explorer_escapes_api_values_in_block_and_transaction_tables():
    probe = f"""
const vm = require('vm');
const script = {json.dumps(JS)};
const elements = {{}};
const element = () => ({{
  innerHTML: '',
  addEventListener() {{}},
  dataset: {{}},
}});
const context = {{
  window: {{ EXPLORER_API_BASE: 'https://example.test' }},
  document: {{
    addEventListener() {{}},
    getElementById(id) {{
      if (!elements[id]) elements[id] = element();
      return elements[id];
    }},
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
const payload = '<img src=x onerror=alert(1)>';
context.payload = payload;
vm.runInContext(`
state.loading.blocks = false;
state.loading.transactions = false;
state.blocks = [{{
  height: 7,
  hash: payload,
  timestamp: Date.now() / 1000,
  miners_count: payload,
  reward: 1
}}];
state.transactions = [{{
  hash: payload,
  type: payload,
  from: payload,
  to: payload,
  amount: 1,
  timestamp: Date.now() / 1000
}}];
renderBlocksTable();
renderTransactionsTable();
`, context);
console.log(JSON.stringify({{
  blocksHtml: elements['blocks-tbody'].innerHTML,
  txHtml: elements['transactions-tbody'].innerHTML,
}}));
"""
    result = subprocess.run(
        ["node", "-e", probe],
        text=True,
        capture_output=True,
        check=True,
    )
    data = json.loads(result.stdout)

    assert "<img" not in data["blocksHtml"]
    assert "<img" not in data["txHtml"]
    assert "&lt;img" in data["blocksHtml"]
    assert "&lt;img" in data["txHtml"]
    assert "0 miners" in data["blocksHtml"]
