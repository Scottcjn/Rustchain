# SPDX-License-Identifier: MIT

from pathlib import Path
import json
import re
import subprocess


AGENT_ECONOMY_HTML = (
    Path(__file__).resolve().parents[1] / "explorer" / "dashboard" / "agent-economy.html"
)


def _source() -> str:
    return AGENT_ECONOMY_HTML.read_text(encoding="utf-8")


def test_agent_economy_job_cards_escape_api_fields():
    source = _source()

    assert "function escapeHtml(value)" in source
    assert "${escapeHtml(job.title)}" in source
    assert "ID: ${escapeHtml(id)}" in source
    assert "${escapeHtml(safeNumber(job.reward).toFixed(1))} RTC" in source
    assert "${escapeHtml(job.description)}" in source
    assert "👤 ${escapeHtml(job.poster)}" in source
    assert "jobs = normalizeJobs(jobsData);" in source

    assert "${job.title}" not in source
    assert "ID: ${job.id}" not in source
    assert "${job.description}" not in source
    assert "👤 ${job.poster}" not in source
    assert "jobs = jobsData;" not in source


def test_agent_economy_uses_safe_category_status_and_wallet_lookup():
    source = _source()

    assert "function safeCategory(value)" in source
    assert "function safeStatus(value)" in source
    assert "function normalizeJobs(payload)" in source
    assert 'class="category-badge ${category}"' in source
    assert "getStatusClass(status, 'open')" in source
    assert "encodeURIComponent(wallet)" in source

    assert 'class="category-badge ${job.category}"' not in source
    assert "getStatusClass(job.status, 'open')" not in source
    assert "agent/reputation/${wallet}" not in source


def test_agent_economy_render_jobs_escapes_malicious_payload():
    script = re.search(
        r"<script>(?P<script>.*?)</script>",
        _source(),
        flags=re.DOTALL,
    ).group("script")
    malicious_jobs_json = json.dumps(
        [
            {
                "id": "job-<bad>",
                "title": "<img src=x onerror=alert(1)>",
                "description": "<script>alert(1)</script>",
                "category": "evil class",
                "reward": "7",
                "status": "badstatus",
                "poster": "<b>attacker</b>",
                "created_at": "2026-05-20T00:00:00Z",
            }
        ]
    )

    probe = f"""
const vm = require('vm');
const script = {json.dumps(script)};
const maliciousJobs = {malicious_jobs_json};
const elements = {{}};
const htmlEscape = (value) => String(value)
  .replace(/&/g, '&amp;')
  .replace(/</g, '&lt;')
  .replace(/>/g, '&gt;');
const element = (id) => ({{
  id,
  value: '',
  dataset: {{}},
  classList: {{ add() {{}}, remove() {{}} }},
  addEventListener() {{}},
  textContent: '',
  get innerHTML() {{ return this._innerHTML || htmlEscape(this.textContent); }},
  set innerHTML(value) {{ this._innerHTML = value; }},
}});
const queryElements = [element('tab-all')];
queryElements[0].dataset.category = 'all';
const context = {{
  console: {{ log() {{}} }},
  setInterval() {{}},
  fetch: async () => ({{ ok: false, json: async () => ({{}}) }}),
  document: {{
    createElement: element,
    querySelectorAll() {{ return queryElements; }},
    getElementById(id) {{
      if (!elements[id]) elements[id] = element(id);
      return elements[id];
    }},
  }},
  alert() {{}},
}};
context.maliciousJobs = maliciousJobs;
vm.createContext(context);
vm.runInContext(script, context);
vm.runInContext('jobs = maliciousJobs; renderJobs();', context);
console.log(JSON.stringify({{ html: elements.jobsGrid.innerHTML }}));
"""
    result = subprocess.run(
        ["node", "-e", probe],
        text=True,
        capture_output=True,
        check=True,
    )
    html = json.loads(result.stdout)["html"]

    assert "&lt;img src=x onerror=alert(1)&gt;" in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "&lt;b&gt;attacker&lt;/b&gt;" in html
    assert 'class="category-badge other"' in html
    assert '<img src=x onerror=alert(1)>' not in html
    assert '<script>alert(1)</script>' not in html
