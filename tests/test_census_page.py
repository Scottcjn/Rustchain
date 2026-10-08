# SPDX-License-Identifier: MIT
"""Runs the Machine Census page's script (census/index.html) under Node with a stubbed
fetch() and a small fake DOM, then checks the rendered output.

The fake DOM serialises text nodes HTML-escaped (as a browser would) and its innerHTML
setter throws, so any use of innerHTML by the page fails these tests.

Covers: /api/miners as the envelope and as a bare array, that miner/wallet ids and IPs
never reach the output, era grouping and counts, the zero-vintage invitation, the
node-unavailable message, verified entries from machines.json, and escaping of a
malicious display name.
"""
import json
import re
import shutil
import subprocess
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "census" / "index.html"
MACHINES = ROOT / "census" / "machines.json"
NODE = shutil.which("node")

NOW = int(time.time())
SECRET_IDS = ["RTCsecretwallet0001", "dual-g4-125-SECRET", "203.0.113.77", "RTCsecretwallet0002"]


def miner(mid, family, arch, hw, mult, **extra):
    m = {"miner": mid, "device_family": family, "device_arch": arch, "hardware_type": hw,
         "antiquity_multiplier": mult, "entropy_score": 0.1,
         "first_attest": 1774820901, "last_attest": NOW - 300}
    m.update(extra)
    return m


MIXED = [
    miner("dual-g4-125-SECRET", "PowerPC", "G4", "PowerPC G4 (Vintage)", 2.5, ip="203.0.113.77"),
    miner("RTCsecretwallet0001", "PowerPC", "G5", "PowerPC G5 (Vintage)", 2.0, wallet="RTCsecretwallet0002"),
    miner("retro-box-SECRET", "x86", "retro", "x86 Retro (Vintage)", 1.4),
    miner("sun-SECRET", "SPARC", "ultrasparc", "SPARC (Exotic)", 2.9),
    miner("modern-a-SECRET", "x86", "broadwell", "x86-64 (Modern)", 1.05),
    miner("modern-b-SECRET", "Apple Silicon", "M2", "Apple Silicon (Modern)", 1.2),
    miner("modern-c-SECRET", "ARM", "aarch64", "Unknown/Other", 0.0005),
]
ALL_SECRETS = SECRET_IDS + [m["miner"] for m in MIXED]

MODERN_ONLY = [MIXED[4], MIXED[5], MIXED[6]]

HARNESS = r"""
const scriptSrc = %(script)s;
const routes = %(routes)s;
function esc(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
class Text { constructor(t) { this.nodeType = 3; this.data = String(t); } }
class Elem {
  constructor(tag) { this.tagName = tag; this.children = []; this.attrs = {}; this.className = ''; this.hidden = false; }
  get firstChild() { return this.children[0] || null; }
  appendChild(c) { this.children.push(c); return c; }
  removeChild(c) { this.children = this.children.filter(x => x !== c); return c; }
  setAttribute(k, v) { this.attrs[k] = String(v); }
  set textContent(t) { this.children = [new Text(t)]; }
  get textContent() { return this.children.map(c => c instanceof Text ? c.data : c.textContent).join(''); }
  set innerHTML(v) { throw new Error('innerHTML must not be used (got: ' + String(v).slice(0, 40) + ')'); }
  get innerHTML() { return this.children.map(ser).join(''); }
}
function ser(n) {
  if (n instanceof Text) return esc(n.data);
  let a = '';
  if (n.className) a += ' class="' + esc(n.className) + '"';
  if (n.hidden) a += ' hidden';
  for (const k of Object.keys(n.attrs)) a += ' ' + k + '="' + esc(n.attrs[k]) + '"';
  return '<' + n.tagName + a + '>' + n.innerHTML + '</' + n.tagName + '>';
}
const els = {};
global.document = {
  getElementById(id) { if (!els[id]) els[id] = new Elem('div'); return els[id]; },
  createElement(tag) { return new Elem(tag); },
};
global.fetch = async (url) => {
  if (!(url in routes)) return { ok: false, status: 404, json: async () => { throw new Error('html'); } };
  const body = routes[url];
  return { ok: true, status: 200, json: async () => JSON.parse(JSON.stringify(body)) };
};
eval(scriptSrc.replace(/^main\(\);$/m, 'global.__main = main;'));
global.__main().then(() => {
  const out = {};
  for (const k of Object.keys(els)) out[k] = { text: els[k].textContent, html: els[k].innerHTML, hidden: els[k].hidden };
  process.stdout.write(JSON.stringify(out));
}).catch(e => { console.error(e); process.exit(1); });
"""

MINERS_URL = "/api/miners?limit=500"


def _page_script():
    html = PAGE.read_text(encoding="utf-8")
    scripts = re.findall(r"<script>(.*?)</script>", html, re.S)
    assert len(scripts) == 1, "expected exactly one inline <script>"
    return scripts[0]


def _run(miners=None, machines=None):
    if not NODE:
        pytest.skip("node not installed")
    routes = {}
    if miners is not None:
        routes[MINERS_URL] = miners
    if machines is not None:
        routes["machines.json"] = machines
    src = HARNESS % {"script": json.dumps(_page_script()), "routes": json.dumps(routes)}
    proc = subprocess.run([NODE, "-e", src], capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def _all_html(dom):
    return "\n".join(v["html"] for v in dom.values())


def _envelope(ms):
    return {"miners": ms, "pagination": {"count": len(ms), "limit": 500, "offset": 0,
                                         "total": len(ms), "total_enrolled": len(ms) + 2}}


@pytest.mark.parametrize("shape", ["envelope", "bare_array"])
def test_live_machines_render_for_both_response_shapes(shape):
    body = _envelope(MIXED) if shape == "envelope" else MIXED
    dom = _run(body, {"schema": 1, "machines": []})
    assert "7 machines are attesting now." == dom["live-status"]["text"]
    assert "PowerPC G4 (1999-2005)" in dom["list-ppc"]["text"]
    assert "2.5×" in dom["list-ppc"]["text"]
    assert "attesting since 2026-03-29" in dom["list-ppc"]["text"]
    assert "seen within the last hour" in dom["list-ppc"]["text"]


def test_no_miner_id_wallet_or_ip_is_ever_rendered():
    for body in (_envelope(MIXED), MIXED):
        out = _all_html(_run(body, {"schema": 1, "machines": []}))
        for secret in ALL_SECRETS:
            assert secret not in out, secret
        assert "SECRET" not in out


def test_era_grouping_and_counts():
    dom = _run(_envelope(MIXED), {"schema": 1, "machines": []})
    assert dom["count-ppc"]["text"] == "2"
    assert dom["count-retro"]["text"] == "1"
    assert dom["count-exotic"]["text"] == "1"
    assert dom["count-modern"]["text"] == "3"
    assert dom["list-ppc"]["html"].count("<li") == 2
    assert dom["list-modern"]["html"].count("<li") == 3
    assert "Retro x86" in dom["list-retro"]["text"]
    assert "SPARC" in dom["list-exotic"]["text"]
    assert "Apple Silicon (2020+)" in dom["list-modern"]["text"]
    for era in ("ppc", "retro", "exotic", "modern"):
        assert dom["empty-" + era]["hidden"] is True


def test_zero_vintage_says_so_with_an_invitation():
    dom = _run(_envelope(MODERN_ONLY), {"schema": 1, "machines": []})
    assert dom["count-ppc"]["text"] == "0"
    assert dom["empty-ppc"]["hidden"] is False
    assert "No G4/G5 machines attesting right now. Own one? Get it on the census." == dom["empty-ppc"]["text"]
    assert 'href="#join"' in dom["empty-ppc"]["html"]
    assert "No retro x86 machines attesting right now." in dom["empty-retro"]["text"]
    assert "No SPARC, MIPS, 68k or classic ARM machines" in dom["empty-exotic"]["text"]
    assert dom["count-modern"]["text"] == "3"


def test_node_failure_is_not_shown_as_zero():
    dom = _run(None, {"schema": 1, "machines": []})
    assert "unavailable" in dom["live-status"]["text"]
    assert "not the same as zero" in dom["live-status"]["text"]
    for era in ("ppc", "retro", "exotic", "modern"):
        assert dom["count-" + era]["text"] == "-"


def test_partial_page_is_reported_honestly():
    body = _envelope(MIXED[:2])
    body["pagination"]["total"] = 40
    dom = _run(body, {"schema": 1, "machines": []})
    assert "The node reports 40; the first 2 are shown." in dom["live-status"]["text"]


def test_shipped_machines_json_is_empty_and_page_says_so():
    shipped = json.loads(MACHINES.read_text(encoding="utf-8"))
    assert shipped == {"schema": 1, "machines": []}
    dom = _run(_envelope(MIXED), shipped)
    assert "No machines have been verified yet" in dom["verified-status"]["text"]
    assert dom["verified-list"]["html"] == ""


def test_verified_entries_render():
    machines = {"schema": 1, "machines": [
        {"model": "Power Mac G4 MDD", "year": 2002, "cpu": "Dual G4 1.25 GHz",
         "photo": "https://example.org/g4.jpg", "photo_alt": "Silver G4 tower",
         "display_name": "", "verified": "2026-10-08", "method": "photo", "tier": "verified",
         "serial_last4": "ZZ99", "issue": 4242},
        {"model": "SPARCstation 20", "year": 1994, "display_name": "Ada",
         "verified": "2026-11-01", "method": "in_person", "event": "VCF Midwest 2026", "tier": "gold",
         "photo": "javascript:alert(1)"},
        {"year": 1999},  # no model: skipped
    ]}
    dom = _run(_envelope(MIXED), machines)
    html, text = dom["verified-list"]["html"], dom["verified-list"]["text"]
    assert dom["verified-status"]["text"] == "2 machines have been verified."
    assert html.count("<li") == 2
    assert text.index("SPARCstation 20") < text.index("Power Mac G4 MDD")  # gold first
    assert "Gold" in text and "Verified" in text
    assert "photo + handwritten code" in text
    assert "in person at VCF Midwest 2026" in text
    assert "Cared for by an anonymous owner" in text and "Cared for by Ada" in text
    assert 'src="https://example.org/g4.jpg"' in html and 'alt="Silver G4 tower"' in html
    assert "javascript:" not in html
    assert "ZZ99" not in html and "4242" not in html


def test_malicious_display_name_is_escaped():
    evil = '<img src=x onerror="alert(1)">'
    machines = {"schema": 1, "machines": [
        {"model": "<script>alert(2)</script>", "display_name": evil, "verified": "2026-10-08",
         "method": "photo", "tier": "verified", "story": "<b>bold</b>"}]}
    evil_miner = miner("x", "<svg onload=alert(3)>", "G4", "<i>x</i>", 2.5)
    dom = _run(_envelope([evil_miner]), machines)
    out = _all_html(dom)
    assert "<img src=x" not in out and "<script>" not in out and "<svg" not in out
    assert "<b>" not in out and "<i>" not in out
    assert "&lt;img src=x onerror=&quot;alert(1)&quot;&gt;" in dom["verified-list"]["html"]
    assert "&lt;script&gt;alert(2)&lt;/script&gt;" in dom["verified-list"]["html"]
    assert "&lt;svg onload=alert(3)&gt;" in dom["list-ppc"]["html"]


def test_static_page_promises_and_instructions():
    html = PAGE.read_text(encoding="utf-8")
    assert "Listing is free and earns no RTC. The census is a preservation record." in html
    assert "RTC CENSUS &lt;your GitHub handle&gt; &lt;today's date&gt;" in html
    assert "issues/new?template=census-submission.yml" in html
    assert ".innerHTML" not in _page_script()
    # No external scripts, styles or fonts (the rustchain.org CSP would block most of them).
    assert not re.search(r"<script[^>]+src=", html)
    assert not re.search(r"<link[^>]+rel=\"stylesheet\"", html)
    assert "@import" not in html and "fonts.googleapis" not in html


def test_issue_form_has_required_fields_and_label():
    form = (ROOT / ".github" / "ISSUE_TEMPLATE" / "census-submission.yml").read_text(encoding="utf-8")
    assert "labels: [census]" in form
    for field_id in ("model", "year", "cpu", "photos", "display-name", "running", "story", "attest"):
        assert f"id: {field_id}" in form
    assert "I own or care for this machine; the photo includes the handwritten code." in form
    assert "Listing is free and earns no RTC." in form
