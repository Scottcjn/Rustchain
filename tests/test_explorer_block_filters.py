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
