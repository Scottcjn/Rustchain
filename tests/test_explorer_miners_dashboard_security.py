# SPDX-License-Identifier: MIT

from pathlib import Path
import json
import re
import subprocess


MINERS_HTML = (
    Path(__file__).resolve().parents[1] / "explorer" / "dashboard" / "miners.html"
)


def _source() -> str:
    return MINERS_HTML.read_text(encoding="utf-8")


def test_miner_rows_escape_api_fields_before_inner_html_rendering():
    source = _source()

    assert "function escapeHtml(value)" in source
    assert "${escapeHtml(id)}" in source
    assert "${escapeHtml(archLabels[arch] || arch)}" in source
    assert "${escapeHtml(multiplier)}x" in source
    assert "${escapeHtml(lastAttestation)}" in source
    assert "${escapeHtml(weight.toLocaleString())}" in source

    assert "<strong>${miner.id}</strong>" not in source
    assert "${archLabels[miner.arch] || miner.arch}" not in source
    assert "${miner.multiplier}x" not in source
    assert "${miner.lastAttestation}" not in source


def test_miner_dashboard_uses_safe_class_tokens_and_current_api_fields():
    source = _source()

    assert "function archClass(arch)" in source
    assert "function minerStatus(miner)" in source
    assert 'class="arch-badge ${archClass(arch)}"' in source
    assert 'class="status-badge ${status}"' in source
    assert "miner.miner_id || miner.miner || miner.wallet" in source
    assert "miner.device_arch || miner.device_family" in source
    assert "miner.multiplier ?? miner.antiquity_multiplier" in source
    assert "miner.lastAttestation ?? miner.last_attestation ?? miner.last_seen ?? miner.last_attest" in source
    assert "function normalizeMinerRows(payload)" in source
    assert "miners = normalizeMinerRows(data);" in source

    assert "miner.arch.toLowerCase().replace(' ', '-')" not in source
    assert 'class="status-badge ${miner.status}"' not in source


def test_malformed_miners_payloads_render_empty_state_without_throwing():
    script = re.search(
        r"<script>(?P<script>.*?)</script>",
        _source(),
        flags=re.DOTALL,
    ).group("script")

    probe = f"""
const vm = require('vm');
const script = {json.dumps(script)};

async function run(payload) {{
  const elements = {{}};
  const htmlEscape = (value) => String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
  const element = () => ({{
    textContent: '',
    value: '',
    addEventListener() {{}},
    get innerHTML() {{ return this._innerHTML || htmlEscape(this.textContent); }},
    set innerHTML(value) {{ this._innerHTML = value; }},
  }});
  const context = {{
    console: {{ log() {{}} }},
    setInterval() {{}},
    fetch: async () => ({{ ok: true, json: async () => payload }}),
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
  await context.fetchMiners();
  return {{
    table: elements.minerTable.innerHTML,
    total: elements.totalMiners.textContent,
  }};
}}

(async () => {{
  const objectPayload = await run({{ miners: {{}} }});
  const nullRows = await run({{ miners: [null] }});
  console.log(JSON.stringify({{ objectPayload, nullRows }}));
}})().catch((error) => {{
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

    assert data["objectPayload"]["total"] == 0
    assert "No miners found" in data["objectPayload"]["table"]
    assert data["nullRows"]["total"] == 0
    assert "No miners found" in data["nullRows"]["table"]
