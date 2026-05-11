from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parent


class SecurityHardeningTests(unittest.TestCase):
    def test_main_explorer_escapes_shortened_api_values(self):
        js = (ROOT / "static/js/explorer.js").read_text()

        self.assertIn("${escapeHtml(shortenAddress(miner.miner_id || 'unknown'))}", js)
        self.assertIn("${escapeHtml(shortenHash(block.hash || '0x'))}", js)
        self.assertIn("${escapeHtml(shortenHash(tx.hash || '0x', 6))}", js)
        self.assertIn("${escapeHtml(shortenAddress(tx.from || '0x'))}", js)
        self.assertIn("${escapeHtml(shortenAddress(tx.to || '0x'))}", js)
        self.assertIn("${escapeHtml(block.miners_count || 0)}", js)

        self.assertNotIn("${shortenAddress(miner.miner_id || 'unknown')}", js)
        self.assertNotIn("${shortenHash(block.hash || '0x')}", js)
        self.assertNotIn("${shortenHash(tx.hash || '0x', 6)}", js)

    def test_realtime_dashboard_escapes_api_values(self):
        js = (ROOT / "static/js/dashboard.js").read_text()

        self.assertIn("escapeHtml(str)", js)
        self.assertIn("${this.escapeHtml(this.shortenAddress(miner.miner_id || 'unknown'))}", js)
        self.assertIn("${this.escapeHtml(miner.device_arch || 'Unknown')}", js)
        self.assertIn("${this.escapeHtml(this.shortenHash(block.hash || '0x'))}", js)
        self.assertIn("${this.escapeHtml((tx.type || 'transfer').toUpperCase())}", js)
        self.assertIn("${this.escapeHtml(this.shortenAddress(tx.from || '0x'))}", js)
        self.assertIn("${this.escapeHtml(this.shortenAddress(tx.to || '0x'))}", js)
        self.assertIn("${this.escapeHtml(item.label)}", js)

    def test_compact_dashboard_escapes_proxied_table_cells(self):
        app = (ROOT / "dashboard/app.py").read_text()

        self.assertIn("function esc(v)", app)
        self.assertIn("${esc(m.miner_id??m.wallet??'-')}", app)
        self.assertIn("${esc(m.score??m.attestation_score??'-')}", app)
        self.assertIn("${esc(m.multiplier??m.antiquity_multiplier??'-')}", app)
        self.assertIn("${esc(t.from??t.sender??'-')}", app)
        self.assertIn("${esc(t.to??t.recipient??'-')}", app)
        self.assertIn("${esc(t.amount??t.value??'-')}", app)

    def test_template_dashboards_escape_api_values(self):
        dashboard = (ROOT / "templates/dashboard.html").read_text()
        ws_dashboard = (ROOT / "templates/ws_explorer.html").read_text()
        miners = (ROOT / "dashboard/miners.html").read_text()
        enhanced = (ROOT / "enhanced-explorer.html").read_text()
        realtime = (ROOT / "realtime-explorer.html").read_text()
        miner_dashboard = (ROOT / "miner-dashboard.html").read_text()
        agent = (ROOT / "dashboard/agent-economy.html").read_text()
        agent_v2 = (ROOT / "dashboard/agent-economy-v2.html").read_text()

        self.assertIn("function escapeHtml(value)", dashboard)
        self.assertIn("${escapeHtml(block.miner)}", dashboard)
        self.assertIn("${escapeHtml(architecture)}", dashboard)
        self.assertIn("encodeURIComponent(block.hash || '')", dashboard)

        self.assertIn("function escapeHtml(value)", ws_dashboard)
        self.assertIn("${escapeHtml(m.miner_id || m.id || '?')}", ws_dashboard)
        self.assertIn("${escapeHtml(a.miner_id)}", ws_dashboard)

        self.assertIn("function escapeHtml(value)", miners)
        self.assertIn("${escapeHtml(minerId)}", miners)
        self.assertIn("${escapeHtml(archLabels[arch] || arch)}", miners)
        self.assertIn("safeClass(arch)", miners)

        self.assertIn("${esc(tx.hash || tx.tx_hash || 'N/A')}", enhanced)
        self.assertIn("${esc(tx.from || 'N/A')}", enhanced)
        self.assertIn("${esc(item.subtitle)}", realtime)
        self.assertIn("${esc(data.total_rtc || 0)}", realtime)
        self.assertIn("shareLink.replaceChildren('Share this dashboard: ', link)", miner_dashboard)
        self.assertIn("${escapeHtml(String(r.amount ?? r.reward ?? r.value ?? '?'))}", miner_dashboard)
        self.assertIn("${esc(job.title)}", agent)
        self.assertIn("${safeClass(job.category)}", agent)
        self.assertIn("encodeURIComponent(wallet)", agent)
        self.assertIn("${esc(j.poster_wallet)}", agent_v2)
        self.assertIn("${safeClass(j.status)}", agent_v2)
        self.assertIn("${esc(a.worker)}", agent_v2)


if __name__ == "__main__":
    unittest.main()
