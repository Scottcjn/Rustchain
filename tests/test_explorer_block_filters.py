# SPDX-License-Identifier: MIT

from pathlib import Path
import json
import subprocess


REPO_ROOT = Path(__file__).resolve().parents[1]
EXPLORER_HTML = REPO_ROOT / "explorer" / "index.html"
EXPLORER_JS = REPO_ROOT / "explorer" / "static" / "js" / "explorer.js"


def test_block_filter_controls_are_available_in_blocks_view():
    html = EXPLORER_HTML.read_text(encoding="utf-8")

    for element_id in (
        "block-filter-proposer",
        "block-filter-from-time",
        "block-filter-to-time",
        "block-filter-min-tx",
        "block-filter-max-tx",
        "block-filter-min-gas",
        "block-filter-max-gas",
        "clear-block-filters",
        "block-filter-summary",
    ):
        assert f'id="{element_id}"' in html

    for heading in (
        "<th scope=\"col\">Proposer</th>",
        "<th scope=\"col\">Txs</th>",
        "<th scope=\"col\">Gas</th>",
    ):
        assert heading in html


def test_miners_table_render_error_uses_text_content():
    js = EXPLORER_JS.read_text(encoding="utf-8")

    assert "UI Render Error: ${escapeHtml(e.message)}" not in js
    assert "function renderMinersTableError(container, message)" in js
    assert "cell.textContent = `UI Render Error: ${message || 'Unknown error'}`;" in js
    assert "container.replaceChildren(row);" in js


def test_block_filter_logic_handles_requested_filter_fields():
    js = EXPLORER_JS.read_text(encoding="utf-8")
    probe = f"""
const vm = require('vm');
const script = {json.dumps(js)};
const context = {{
  window: {{ EXPLORER_API_BASE: 'https://example.test' }},
  document: {{
    addEventListener() {{}},
    getElementById() {{ return null; }},
    querySelectorAll() {{ return []; }},
  }},
  console: {{ log() {{}}, error() {{}} }},
  setInterval() {{ return 1; }},
  clearInterval() {{}},
  setTimeout() {{ return 1; }},
  clearTimeout() {{}},
  fetch() {{ throw new Error('network disabled in test'); }},
  AbortController: function() {{ this.signal = {{}}; this.abort = function() {{}}; }},
}};
vm.createContext(context);
vm.runInContext(script, context);
const result = vm.runInContext(`
  const api = window.RustChainExplorer;
  api.state.blocks = [
    {{
      height: 3,
      proposer: 'alice',
      timestamp: '2026-06-03T10:00:00',
      tx_count: 8,
      gas_used: 12000
    }},
    {{
      height: 2,
      miner: 'bob',
      timestamp: '2026-06-03T09:00:00',
      transactions: [{{}}, {{}}],
      total_gas_used: 4000
    }},
    {{
      height: 1,
      producer: 'alice-backup',
      timestamp: '2026-06-03T08:00:00',
      transactions_count: 3,
      gasUsed: 9000
    }}
  ];
  api.state.blockFilters = {{
    proposer: 'alice',
    fromTime: '2026-06-03T08:30',
    toTime: '2026-06-03T10:30',
    minTransactions: '4',
    maxTransactions: '10',
    minGas: '10000',
    maxGas: '13000'
  }};
  JSON.stringify({{
    filteredHeights: api.filterBlocks().map(block => block.height),
    envelopeHeights: normalizeBlocksResponse({{ blocks: [{{ height: 9 }}, null, 'bad'] }}).map(block => block.height)
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

    assert data["filteredHeights"] == [3]
    assert data["envelopeHeights"] == [9]


def test_all_blocks_filter_uses_untruncated_fetched_blocks():
    js = EXPLORER_JS.read_text(encoding="utf-8")
    probe = f"""
const vm = require('vm');
const script = {json.dumps(js)};

(async () => {{
  const elements = {{}};
  const elementFor = id => {{
    if (!elements[id]) {{
      elements[id] = {{
        value: '',
        innerHTML: '',
        textContent: '',
        addEventListener() {{}},
        classList: {{ toggle() {{}}, add() {{}}, remove() {{}} }},
        setAttribute() {{}},
        removeAttribute() {{}}
      }};
    }}
    return elements[id];
  }};
  const context = {{
    window: {{ EXPLORER_API_BASE: 'https://example.test' }},
    document: {{
      addEventListener() {{}},
      getElementById: elementFor,
      querySelectorAll() {{ return []; }},
      querySelector() {{ return null; }},
    }},
    console: {{ log() {{}}, error() {{}} }},
    setInterval() {{ return 1; }},
    clearInterval() {{}},
    setTimeout() {{ return 1; }},
    clearTimeout() {{}},
    fetch(url) {{
      const blocks = [
        {{ height: 103, hash: '0x103', timestamp: '2026-06-03T10:00:00', proposer: 'recent-a', tx_count: 1, gas_used: 100 }},
        {{ height: 102, hash: '0x102', timestamp: '2026-06-03T09:00:00', proposer: 'recent-b', tx_count: 2, gas_used: 200 }},
        {{ height: 101, hash: '0x101', timestamp: '2026-06-03T08:00:00', proposer: 'archive-miner', tx_count: 9, gas_used: 900 }}
      ];
      const payload = url.endsWith('/blocks') ? blocks :
        (url.endsWith('/api/miners') ? [] :
        (url.endsWith('/api/transactions') ? [] :
        (url.endsWith('/epoch') ? {{ epoch: 1, slot: 1, blocks_per_epoch: 144 }} :
        {{ status: 'ok', version: 'test' }})));
      return Promise.resolve({{ ok: true, json: () => Promise.resolve(payload) }});
    }},
    AbortController: function() {{ this.signal = {{}}; this.abort = function() {{}}; }},
  }};
  vm.createContext(context);
  vm.runInContext(script, context);
  const result = await vm.runInContext(`
    (async () => {{
      const api = window.RustChainExplorer;
      api.CONFIG.MAX_RECENT_BLOCKS = 2;
      await api.refresh();
      api.setBlockFilters({{ proposer: 'archive-miner' }});
      return JSON.stringify({{
        storedBlockCount: api.state.blocks.length,
        summary: document.getElementById('block-filter-summary').textContent,
        recentHtml: document.getElementById('blocks-tbody').innerHTML,
        fullHtml: document.getElementById('blocks-tbody-full').innerHTML,
        filteredHeights: api.filterBlocks().map(block => block.height)
      }});
    }})()
  `, context);
  console.log(result);
}})().catch(error => {{
  console.error(error);
  process.exit(1);
}});
"""
    result = subprocess.run(
        ["node", "-e", probe],
        text=True,
        capture_output=True,
        check=True,
    )
    data = json.loads(result.stdout)

    assert data["storedBlockCount"] == 3
    assert data["summary"] == "1 of 3 blocks"
    assert data["filteredHeights"] == [101]
    assert "#101" not in data["recentHtml"]
    assert "#101" in data["fullHtml"]
