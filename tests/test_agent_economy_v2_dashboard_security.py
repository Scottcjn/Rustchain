# SPDX-License-Identifier: MIT

from pathlib import Path
import json
import re
import subprocess


AGENT_ECONOMY_V2_HTML = (
    Path(__file__).resolve().parents[1]
    / "explorer"
    / "dashboard"
    / "agent-economy-v2.html"
)


def _source() -> str:
    return AGENT_ECONOMY_V2_HTML.read_text(encoding="utf-8")


def test_agent_economy_v2_defines_render_safety_helpers():
    source = _source()

    assert "function safeNumber(value, fallback = 0)" in source
    assert "function safeStatus(value)" in source
    assert "function safeCategory(value)" in source
    assert "function safeTrustLevel(value)" in source
    assert "function normalizeJobs(payload)" in source
    assert "d.textContent = String(s ?? '');" in source


def test_agent_economy_v2_escapes_job_and_reputation_fields():
    source = _source()

    safe_patterns = [
        "const status = safeStatus(j.status);",
        "const category = safeCategory(j.category);",
        'class="badge badge-${status}"',
        "${esc(j.worker_wallet)}",
        "${esc(j.poster_wallet)}",
        "${esc(j.job_id)}",
        "allJobs = results.flatMap(r => normalizeJobs(r));",
        "encodeURIComponent(w)",
        "const trustLevel = safeTrustLevel(a.trust_level);",
        "${esc(a.wallet)}",
    ]

    for pattern in safe_patterns:
        assert pattern in source

    unsafe_patterns = [
        'class="badge badge-${j.status}"',
        "${j.worker_wallet}",
        "${j.poster_wallet}",
        "${j.job_id}",
        "allJobs = results.flatMap(r => r.jobs || []);",
        "agent/reputation/${w}",
        "${a.wallet}",
        "${a.trust_level || 'neutral'}",
    ]

    for pattern in unsafe_patterns:
        assert pattern not in source


def test_agent_economy_v2_escapes_malicious_job_payload():
    script = re.search(
        r"<script>(?P<script>.*?)</script>",
        _source(),
        flags=re.DOTALL,
    ).group("script")
    malicious_jobs_json = json.dumps(
        [
            {
                "job_id": "job-<bad>",
                "title": "<img src=x onerror=alert(1)>",
                "description": "<script>alert(1)</script>",
                "category": "evil class",
                "status": "closed danger",
                "reward_rtc": "nan",
                "worker_wallet": "<b>worker</b>",
                "poster_wallet": "<i>poster</i>",
                "tags": json.dumps(["<svg onload=alert(1)>"]),
                "created_at": "bad-time",
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
  classList: {{ add() {{}}, remove() {{}} }},
  addEventListener() {{}},
  textContent: '',
  get innerHTML() {{ return this._innerHTML || htmlEscape(this.textContent); }},
  set innerHTML(value) {{ this._innerHTML = value; }},
}});
elements['category-filter'] = element('category-filter');
const context = {{
  console: {{ log() {{}} }},
  setInterval() {{}},
  fetch: async () => ({{ ok: false, json: async () => ({{}}) }}),
  document: {{
    createElement: element,
    querySelectorAll() {{ return []; }},
    addEventListener() {{}},
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
vm.runInContext('allJobs = maliciousJobs; renderJobs();', context);
console.log(JSON.stringify({{ html: elements['jobs-grid'].innerHTML }}));
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
    assert "&lt;b&gt;worker&lt;/b&gt;" in html
    assert "&lt;i&gt;poster&lt;/i&gt;" in html
    assert "&lt;svg onload=alert(1)&gt;" in html
    assert "badge badge-unknown" in html
    assert "badge badge-open" not in html
    assert ">other<" in html
    assert "<img src=x onerror=alert(1)>" not in html
    assert "<script>alert(1)</script>" not in html


def test_agent_economy_v2_keeps_translation_jobs_filterable():
    script = re.search(
        r"<script>(?P<script>.*?)</script>",
        _source(),
        flags=re.DOTALL,
    ).group("script")
    translation_jobs_json = json.dumps(
        [
            {
                "job_id": "translation-1",
                "title": "Translate docs",
                "description": "Translate user guide",
                "category": "translation",
                "status": "open",
                "reward_rtc": 3,
                "poster_wallet": "alice",
                "created_at": 1_700_000_000,
            }
        ]
    )

    probe = f"""
const vm = require('vm');
const script = {json.dumps(script)};
const translationJobs = {translation_jobs_json};
const elements = {{}};
const htmlEscape = (value) => String(value)
  .replace(/&/g, '&amp;')
  .replace(/</g, '&lt;')
  .replace(/>/g, '&gt;');
const element = (id) => ({{
  id,
  value: '',
  classList: {{ add() {{}}, remove() {{}} }},
  addEventListener() {{}},
  textContent: '',
  get innerHTML() {{ return this._innerHTML || htmlEscape(this.textContent); }},
  set innerHTML(value) {{ this._innerHTML = value; }},
}});
elements['category-filter'] = element('category-filter');
elements['category-filter'].value = 'translation';
const context = {{
  console: {{ log() {{}} }},
  setInterval() {{}},
  fetch: async () => ({{ ok: false, json: async () => ({{}}) }}),
  document: {{
    createElement: element,
    querySelectorAll() {{ return []; }},
    addEventListener() {{}},
    getElementById(id) {{
      if (!elements[id]) elements[id] = element(id);
      return elements[id];
    }},
  }},
  alert() {{}},
}};
context.translationJobs = translationJobs;
vm.createContext(context);
vm.runInContext(script, context);
vm.runInContext('allJobs = translationJobs; currentStatus = "open"; renderJobs();', context);
console.log(JSON.stringify({{ html: elements['jobs-grid'].innerHTML }}));
"""
    result = subprocess.run(
        ["node", "-e", probe],
        text=True,
        capture_output=True,
        check=True,
    )
    html = json.loads(result.stdout)["html"]

    assert "Translate docs" in html
    assert ">translation<" in html
    assert "No jobs found" not in html
