#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
Tests for wRTC Bridge Dashboard
Run: python -m pytest tools/wrtc-bridge-dashboard/test_bridge_dashboard.py -v
"""

import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))


class TestHTMLStructure(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(HERE, "index.html"), encoding="utf-8") as f:
            cls.html = f.read()

    def test_has_title(self):
        self.assertIn("wRTC Bridge Dashboard", self.html)

    def test_has_stats(self):
        for sid in ["rtc-locked", "wrtc-supply", "wrtc-price", "fee-revenue", "volume-24h"]:
            self.assertIn(f'id="{sid}"', self.html)

    def test_has_health_badge(self):
        self.assertIn('id="health-badge"', self.html)

    def test_has_tx_tables(self):
        self.assertIn('id="wrap-table"', self.html)
        self.assertIn('id="unwrap-table"', self.html)

    def test_has_price_chart(self):
        self.assertIn('id="price-chart"', self.html)
        self.assertIn('id="chart-line"', self.html)

    def test_has_refresh_timer(self):
        self.assertIn('id="last-update"', self.html)

    def test_responsive(self):
        self.assertIn("viewport", self.html)
        self.assertIn("grid-template-columns", self.html)

    def test_loads_js(self):
        self.assertIn("bridge_dashboard.js", self.html)

    def test_no_external_deps(self):
        # No React, no framework CDN — pure vanilla
        self.assertNotIn("react", self.html.lower())
        self.assertNotIn("vue", self.html.lower())


class TestJSStructure(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(HERE, "bridge_dashboard.js"), encoding="utf-8") as f:
            cls.js = f.read()

    def test_rustchain_api(self):
        self.assertIn("rustchain.org", self.js)

    def test_solana_rpc(self):
        self.assertIn("mainnet-beta.solana.com", self.js)

    def test_dexscreener(self):
        self.assertIn("dexscreener", self.js)

    def test_fetches_locked(self):
        self.assertIn("fetchRTCLocked", self.js)
        self.assertIn("bridge-escrow", self.js)

    def test_fetches_supply(self):
        self.assertIn("fetchWRTCSupply", self.js)
        self.assertIn("getTokenSupply", self.js)

    def test_fetches_price(self):
        self.assertIn("fetchWRTCPrice", self.js)
        self.assertIn("priceUsd", self.js)

    def test_fetches_health(self):
        self.assertIn("fetchBridgeHealth", self.js)

    def test_fetches_transactions(self):
        self.assertIn("fetchBridgeTransactions", self.js)

    def test_has_demo_fallback(self):
        self.assertIn("demoData", self.js)

    def test_auto_refresh(self):
        self.assertIn("setInterval", self.js)
        self.assertIn("REFRESH_MS", self.js)

    def test_time_ago(self):
        self.assertIn("timeAgo", self.js)

    def test_chart_update(self):
        self.assertIn("updateChart", self.js)
        self.assertIn("chart-line", self.js)

    def test_health_states(self):
        self.assertIn("health-ok", self.js)
        self.assertIn("health-err", self.js)
        self.assertIn("health-warn", self.js)

    def test_wrap_unwrap_types(self):
        self.assertIn('"wrap"', self.js)
        self.assertIn('"unwrap"', self.js)

    def test_price_change_color(self):
        self.assertIn("#22c55e", self.js)  # green for positive
        self.assertIn("#ef4444", self.js)  # red for negative

    def test_transaction_fields_are_escaped_before_inner_html(self):
        self.assertIn("function escapeHtml(value)", self.js)
        self.assertIn("function safeBridgeType(value)", self.js)
        self.assertIn("function shortTx(value)", self.js)
        self.assertIn("${escapeHtml(tx.wallet)}", self.js)
        self.assertIn("${escapeHtml(shortTx(tx.tx))}", self.js)
        self.assertIn("${escapeHtml(fmt(tx.amount))}", self.js)
        self.assertNotIn("${tx.wallet}", self.js)
        self.assertNotIn("${tx.tx.slice(0, 8)}", self.js)

    def test_update_tx_table_escapes_malicious_transaction_rows(self):
        js_path = Path(HERE) / "bridge_dashboard.js"
        probe = f"""
const fs = require("fs");
const vm = require("vm");
let script = fs.readFileSync({str(js_path)!r}, "utf8");
script = script.replace(/\\nrefresh\\(\\);\\nsetInterval\\(refresh, REFRESH_MS\\);\\s*$/, "");
const elements = {{
  "wrap-table": {{ innerHTML: "" }}
}};
const context = {{
  document: {{ getElementById: id => elements[id] || (elements[id] = {{ innerHTML: "", textContent: "", style: {{}}, setAttribute() {{}} }}) }},
  Date,
  Math,
  console,
  fetch() {{ throw new Error("network disabled in test"); }},
  setInterval() {{}}
}};
vm.createContext(context);
vm.runInContext(script, context);
vm.runInContext(`
  updateTxTable("wrap-table", [{{
    time: new Date().toISOString(),
    amount: "<img src=x>",
    wallet: "<img src=x onerror=alert(1)>",
    tx: "<script>alert(2)</script>",
    type: "<b>bad</b>"
  }}]);
`, context);
console.log(elements["wrap-table"].innerHTML);
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            probe_path = Path(tmpdir) / "probe.js"
            probe_path.write_text(probe, encoding="utf-8")
            result = subprocess.run(
                ["node", str(probe_path)],
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=True,
            )

        html = result.stdout
        self.assertIn("&lt;img src=x onerror=alert(1)&gt;", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("wRTC", html)
        self.assertNotIn("<img src=x onerror=alert(1)>", html)
        self.assertNotIn("<script>alert(2)</script>", html)


class TestStaticDeploy(unittest.TestCase):
    def test_files_exist(self):
        for f in ["index.html", "bridge_dashboard.js"]:
            self.assertTrue(os.path.exists(os.path.join(HERE, f)))

    def test_no_build_required(self):
        self.assertFalse(os.path.exists(os.path.join(HERE, "package.json")))

    def test_valid_html(self):
        with open(os.path.join(HERE, "index.html"), encoding="utf-8") as f:
            html = f.read()
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("</html>", html)


if __name__ == "__main__":
    unittest.main()
