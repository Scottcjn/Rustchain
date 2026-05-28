# SPDX-License-Identifier: MIT
import json
from pathlib import Path
import subprocess


APP = Path(__file__).resolve().parents[1] / "explorer" / "dashboard" / "app.py"


def test_explorer_dashboard_app_renders_rows_with_dom_text_nodes():
    source = APP.read_text(encoding="utf-8")

    safe_patterns = [
        "function asObject(v)",
        "function asArray(v)",
        "function asRows(v,key)",
        "!Array.isArray(x)",
        "function firstPresent(...values)",
        "function text(v,f='-')",
        "function td(v)",
        "cell.textContent=text(v);",
        "function renderRows(tbodyId,rows,limit,mapper,emptyText)",
        "tbody.replaceChildren(...body);",
        "renderRows('minersTbl',miners,20",
        "renderRows('txTbl',transactions,30",
    ]

    for pattern in safe_patterns:
        assert pattern in source

    unsafe_patterns = [
        "document.getElementById('minersTbl').innerHTML=(d.miners||[])",
        "document.getElementById('txTbl').innerHTML=(d.transactions||[])",
        "<td>${m.miner_id||m.wallet||'-'}</td>",
        "<td>${t.from||t.sender||'-'}</td>",
    ]

    for pattern in unsafe_patterns:
        assert pattern not in source


def test_explorer_dashboard_app_normalizes_dashboard_payloads():
    source = APP.read_text(encoding="utf-8")

    assert "const d=asObject(await j('/api/dashboard'));" in source
    assert "const miners=asRows(d.miners,'miners');" in source
    assert "const transactions=asRows(d.transactions,'transactions');" in source
    assert "document.getElementById('network').textContent=text(asObject(d.health).status,'unknown');" in source
    assert "document.getElementById('epoch').textContent=text(asObject(d.epoch).epoch);" in source
    assert "document.getElementById('miners').textContent=miners.length;" in source
    assert "document.getElementById('txcount').textContent=transactions.length;" in source
    assert "firstPresent(m.miner_id,m.wallet,m.miner)" in source
    assert "firstPresent(m.score,m.attestation_score,m.entropy_score)" in source
    assert "firstPresent(m.multiplier,m.antiquity_multiplier)" in source
    assert "firstPresent(t.amount,t.value)" in source


def test_explorer_dashboard_app_preserves_zero_values_and_rejects_nested_arrays():
    source = APP.read_text(encoding="utf-8")

    assert "v!==undefined&&v!==null&&v!==''" in source
    assert "m.score||m.attestation_score" not in source
    assert "m.multiplier||m.antiquity_multiplier" not in source
    assert "t.amount||t.value" not in source
    assert "typeof x==='object'&&!Array.isArray(x)" in source


def test_explorer_dashboard_app_renders_live_miners_wrapper_payload():
    source = APP.read_text(encoding="utf-8")
    script = source.split("<script>", 1)[1].split("</script>", 1)[0]

    probe = f"""
const vm = require('vm');
const script = {json.dumps(script)};
const elements = {{}};
const element = () => ({{
  textContent: '',
  children: [],
  colSpan: 0,
  append(...nodes) {{ this.children.push(...nodes); }},
  appendChild(node) {{ this.children.push(node); }},
  replaceChildren(...nodes) {{ this.children = nodes; }},
}});
const dashboardPayload = {{
  base: 'https://node.example',
  health: {{ status: 'ok' }},
  epoch: {{ epoch: 0 }},
  miners: {{
    miners: [
      {{ miner: 'power8-s824-sophia', entropy_score: 0, antiquity_multiplier: 2.0 }},
    ],
    pagination: {{ total: 1 }},
  }},
  transactions: [],
}};
const context = {{
  setInterval() {{}},
  fetch: async () => ({{ json: async () => dashboardPayload }}),
  document: {{
    createElement(tag) {{
      const node = element();
      node.tagName = tag;
      return node;
    }},
    getElementById(id) {{
      if (!elements[id]) elements[id] = element();
      return elements[id];
    }},
  }},
}};
vm.createContext(context);
vm.runInContext(script, context);
context.load().then(() => {{
  const row = elements.minersTbl.children[0];
  console.log(JSON.stringify({{
    minersText: String(elements.miners.textContent),
    firstRow: row.children.map(cell => cell.textContent),
  }}));
}}).catch((error) => {{
  console.error(error);
  process.exit(1);
}});
"""
    result = subprocess.run(
        ["node", "-e", probe],
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=True,
    )
    rendered = json.loads(result.stdout)

    assert rendered["minersText"] == "1"
    assert rendered["firstRow"] == ["power8-s824-sophia", "0", "2"]
