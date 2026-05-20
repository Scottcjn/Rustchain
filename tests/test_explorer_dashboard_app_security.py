# SPDX-License-Identifier: MIT

import importlib.util
import json
import subprocess
from pathlib import Path


APP_PATH = Path(__file__).resolve().parents[1] / "explorer" / "dashboard" / "app.py"


def _source() -> str:
    return APP_PATH.read_text(encoding="utf-8")


def _load_module():
    spec = importlib.util.spec_from_file_location("explorer_dashboard_app_under_test", APP_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    module.app.config["TESTING"] = True
    return module


def test_dashboard_table_rows_escape_api_fields_before_inner_html():
    source = _source()

    assert "function escapeHtml(value)" in source
    assert "function displayValue(value)" in source
    assert "${displayValue(m.miner_id??m.wallet)}" in source
    assert "${displayValue(m.score??m.attestation_score)}" in source
    assert "${displayValue(m.multiplier??m.antiquity_multiplier)}" in source
    assert "${escapeHtml(fmtTs(t.timestamp??t.created_at??t.time))}" in source
    assert "${displayValue(t.from??t.sender)}" in source
    assert "${displayValue(t.to??t.recipient)}" in source
    assert "${displayValue(t.amount??t.value)}" in source

    assert "${m.miner_id||m.wallet||'-'}" not in source
    assert "${displayValue(m.score||m.attestation_score)}" not in source
    assert "${t.from||t.sender||'-'}" not in source
    assert "${displayValue(t.amount||t.value)}" not in source
    assert "${t.to||t.recipient||'-'}" not in source


def test_dashboard_api_normalizes_paginated_rows(monkeypatch):
    module = _load_module()

    def fake_fetch(path):
        responses = {
            "/health": {"status": "ok"},
            "/api/miners": {"miners": [{"miner_id": "miner-1"}], "pagination": {"total": 1}},
            "/epoch": {"epoch": 42},
            "/api/transactions": {
                "transactions": [{"from": "alice", "to": "bob"}],
                "pagination": {"total": 1},
            },
        }
        return responses[path]

    monkeypatch.setattr(module, "fetch_json", fake_fetch)

    response = module.app.test_client().get("/api/dashboard")

    assert response.status_code == 200
    data = response.get_json()
    assert data["miners"] == [{"miner_id": "miner-1"}]
    assert data["transactions"] == [{"from": "alice", "to": "bob"}]


def test_dashboard_frontend_preserves_zero_values():
    source = _source()
    script = source.split("<script>", 1)[1].split("</script>", 1)[0]

    probe = f"""
const vm = require('vm');
const script = {json.dumps(script)};
const elements = {{}};
const htmlEscape = (value) => String(value)
  .replace(/&/g, '&amp;')
  .replace(/</g, '&lt;')
  .replace(/>/g, '&gt;');
const element = () => ({{
  textContent: '',
  get innerHTML() {{ return this._innerHTML || htmlEscape(this.textContent); }},
  set innerHTML(value) {{ this._innerHTML = value; }},
}});
const dashboardPayload = {{
  base: 'https://node.example',
  health: {{ status: 'ok' }},
  epoch: {{ epoch: 0 }},
  miners: [{{ miner_id: 'miner-zero', score: 0, attestation_score: 7, multiplier: 0, antiquity_multiplier: 3 }}],
  transactions: [{{ timestamp: 0, created_at: 1779250000, from: 'alice', to: 'bob', amount: 0, value: 9 }}],
}};
const context = {{
  setInterval() {{}},
  fetch: async () => ({{ json: async () => dashboardPayload }}),
  document: {{
    createElement: element,
    getElementById(id) {{
      if (!elements[id]) elements[id] = element();
      return elements[id];
    }},
  }},
}};
vm.createContext(context);
vm.runInContext(script, context);
context.load().then(() => {{
  console.log(JSON.stringify({{
    miners: elements.minersTbl.innerHTML,
    txs: elements.txTbl.innerHTML,
  }}));
}}).catch((error) => {{
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
    rendered = json.loads(result.stdout)

    assert "<td>0</td><td>0</td>" in rendered["miners"]
    assert "<td>0</td>" in rendered["txs"]
    assert "<td>7</td>" not in rendered["miners"]
    assert "<td>9</td>" not in rendered["txs"]
