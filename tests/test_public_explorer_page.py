# SPDX-License-Identifier: MIT
"""Runs the public explorer page's script (explorer/public_node/explorer.html) under Node
with a stubbed fetch() and document, and checks what ends up in the DOM.

Covers: /api/miners as a bare array and as the {"miners": [...]} envelope, the agent
endpoints returning 404 (rustchain.org has no nginx route for /agent/*), and HTML
escaping of node-supplied strings.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

PAGE = Path(__file__).resolve().parents[1] / "explorer" / "public_node" / "explorer.html"
NODE = shutil.which("node")

MINER = {
    "miner": "dual-g4-125",
    "device_arch": "G4",
    "device_family": "PowerPC",
    "hardware_type": "PowerPC G4",
    "antiquity_multiplier": 2.5,
    "last_attest": 0,  # replaced with "now" inside the harness
}
EVIL = dict(MINER, miner='<img src=x onerror="alert(1)">', hardware_type="<b>x</b>")

HARNESS = r"""
const scriptSrc = %(script)s;
const routes = %(routes)s;
const els = {};
function el(id) {
  if (!els[id]) els[id] = { id, textContent: '', innerHTML: '', className: '', style: {} };
  return els[id];
}
global.document = { getElementById: el };
global.setInterval = () => 0;
global.setTimeout = () => 0;
const now = Math.floor(Date.now() / 1000);
global.fetch = async (url) => {
  const r = routes[url];
  if (!r) return { ok: false, status: 404, json: async () => { throw new Error('html'); } };
  const body = JSON.parse(JSON.stringify(r).replace(/"last_attest":0/g, '"last_attest":' + now));
  return { ok: true, status: 200, json: async () => body };
};
// The page calls refresh() at top level; expose it so we can await it.
eval(scriptSrc.replace(/^refresh\(\);$/m, 'global.__refresh = refresh;'));
global.__refresh().then(() => {
  const out = {};
  for (const k of Object.keys(els)) out[k] = { text: String(els[k].textContent), html: String(els[k].innerHTML) };
  process.stdout.write(JSON.stringify(out));
}).catch(e => { console.error(e); process.exit(1); });
"""


def _page_script():
    html = PAGE.read_text(encoding="utf-8")
    m = re.search(r"<script>(.*?)</script>", html, re.S)
    assert m, "inline <script> not found"
    return m.group(1)


def _run(routes):
    if not NODE:
        pytest.skip("node not installed")
    src = HARNESS % {"script": json.dumps(_page_script()), "routes": json.dumps(routes)}
    proc = subprocess.run([NODE, "-e", src], capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


BASE = {
    "/health": {"ok": True, "version": "2.2.1-rip200", "uptime_s": 100, "db_rw": True},
    "/epoch": {"epoch": 308, "slot": 44382, "blocks_per_epoch": 144, "epoch_pot": 1.5,
               "total_supply_rtc": 8388608, "enrolled_miners": 1},
}


@pytest.mark.parametrize("shape", ["bare_array", "envelope"])
def test_miners_table_renders_for_both_response_shapes(shape):
    miners = [MINER]
    body = miners if shape == "bare_array" else {
        "miners": miners, "pagination": {"count": 1, "limit": 100, "offset": 0, "total": 1}}
    dom = _run(dict(BASE, **{"/api/miners": body}))
    assert "dual-g4-125" in dom["minerTableBody"]["html"]
    assert "Loading miners" not in dom["minerTableBody"]["html"]
    assert dom["minerCount"]["text"] == "1"


def test_miners_failure_and_empty_are_reported():
    dom = _run(dict(BASE))  # /api/miners -> 404
    assert "unavailable" in dom["minerTableBody"]["html"]
    dom = _run(dict(BASE, **{"/api/miners": {"miners": [], "pagination": {"total": 0}}}))
    assert "No miners" in dom["minerTableBody"]["html"]
    assert dom["minerCount"]["text"] == "0"


def test_agent_panel_says_unavailable_when_agent_routes_404():
    dom = _run(dict(BASE, **{"/api/miners": {"miners": [MINER]}}))
    assert dom["agentVolume"]["text"] == "unavailable"
    assert dom["openJobs"]["text"] == "unavailable"
    assert "unavailable" in dom["jobsList"]["html"]
    assert "No jobs in marketplace" not in dom["jobsList"]["html"]


def test_agent_panel_renders_when_routes_exist():
    stats = {"ok": True, "stats": {"total_rtc_volume": 1096.83, "completed_jobs": 177,
                                   "total_fees_collected": 54.84, "open_jobs": 0,
                                   "escrow_balance_rtc": 86.11}}
    job = {"title": "<script>alert(1)</script>", "status": "open", "category": "code",
           "poster_wallet": "w<1>", "worker_wallet": None, "expires_at": 0,
           "reward_rtc": 5, "description": "<img src=x onerror=alert(2)> long enough text"}
    dom = _run(dict(BASE, **{"/agent/stats": stats, "/agent/jobs": {"ok": True, "jobs": [job]},
                             "/api/miners": {"miners": [MINER]}}))
    assert dom["openJobs"]["text"] == "0"
    html = dom["jobsList"]["html"]
    assert "&lt;script&gt;" in html and "<script>" not in html
    assert "<img" not in html and "w&lt;1&gt;" in html
    dom = _run(dict(BASE, **{"/agent/stats": stats, "/agent/jobs": {"ok": True, "jobs": []},
                             "/api/miners": {"miners": [MINER]}}))
    assert "No jobs in marketplace" in dom["jobsList"]["html"]


def test_miner_fields_are_html_escaped():
    dom = _run(dict(BASE, **{"/api/miners": {"miners": [EVIL]}}))
    html = dom["minerTableBody"]["html"]
    assert "<img" not in html and "<b>" not in html
    assert "&lt;b&gt;x&lt;/b&gt;" in html


def test_anchors_link_is_relative():
    # Absolute /anchors 404s on rustchain.org (page lives under /explorer/).
    html = PAGE.read_text(encoding="utf-8")
    assert 'href="/anchors"' not in html
    assert 'href="anchors"' in html
