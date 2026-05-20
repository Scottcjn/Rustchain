# SPDX-License-Identifier: MIT

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BRIDGE_DASHBOARD = ROOT / "static" / "bridge" / "dashboard.html"


def test_bridge_dashboard_scripts_parse_as_javascript():
    script = """
const fs = require('fs');
const html = fs.readFileSync(process.argv[1], 'utf8');
const scripts = [...html.matchAll(/<script[^>]*>([\\s\\S]*?)<\\/script>/g)];
if (scripts.length === 0) throw new Error('script block missing');
for (const [index, match] of scripts.entries()) {
  try {
    new Function(match[1]);
  } catch (error) {
    throw new Error(`script ${index}: ${error.message}`);
  }
}
"""

    subprocess.run(
        ["node", "-e", script, str(BRIDGE_DASHBOARD)],
        check=True,
        cwd=ROOT,
    )


def test_bridge_dashboard_has_no_mojibake_arrow_literals():
    html = BRIDGE_DASHBOARD.read_text(encoding="utf-8")

    assert "'鈫?" not in html
    assert "鉁?" not in html
    assert "鈫?/div>" not in html
    assert "RTC鈫" not in html
